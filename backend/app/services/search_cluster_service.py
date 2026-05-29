"""
Search Cluster Service — demand-driven role discovery.

Clusters similar search queries using pgvector cosine similarity.
Thresholds:
  - min_search (5): cluster appears in admin "Role Requests"
  - max_search (50): auto-create role without admin review
"""

import json
import re
import hashlib
from uuid import uuid4

from sqlalchemy import text as sa_text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.embedding_service import get_embedding
from app.services.llm_client import call_llm

logger = get_logger(__name__)

# ── Config ───────────────────────────────────────────────────────────
SEARCH_MIN_THRESHOLD = 5
SEARCH_MAX_THRESHOLD = 50
SIMILARITY_THRESHOLD = 0.75
RATE_LIMIT_PER_IP = 10  # per minute


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:60]


# ── Rate limiting (Redis) ────────────────────────────────────────────
async def check_rate_limit(redis, fingerprint: str) -> bool:
    """Return True if rate limit NOT exceeded (allowed)."""
    if redis is None:
        return True
    key = f"rate:search:{fingerprint}"
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, 60)
        return current <= RATE_LIMIT_PER_IP
    except Exception:
        return True


# ── Core: Process a search query ─────────────────────────────────────
async def process_search(
    query: str,
    user_fingerprint: str,
    db: AsyncSession,
    redis=None,
) -> dict:
    """
    Process a user search:
    1. Embed query
    2. Find matching cluster or create new
    3. Check thresholds
    4. Return matched templates + cluster status
    """
    query = query.strip()
    if not query or len(query) < 3:
        return {"results": [], "message": "Query terlalu pendek."}

    # Rate limit
    if not await check_rate_limit(redis, user_fingerprint):
        return {"results": [], "message": "Terlalu banyak pencarian. Coba lagi nanti."}

    # Embed
    embedding = await get_embedding(query)
    if not embedding:
        return {"results": [], "message": "Gagal memproses pencarian."}

    embedding_str = json.dumps(embedding)

    # Find matching templates
    templates = await _match_templates(query, db)

    # Find or create cluster
    cluster_id = await _find_or_create_cluster(
        query, embedding_str, user_fingerprint, db
    )

    # Get cluster status
    cluster = await _get_cluster(cluster_id, db)

    message = ""
    suggestions = []
    if templates:
        message = f"Ditemukan {len(templates)} staff yang cocok."
    else:
        # No exact match — find skill-similar templates as suggestions
        suggestions = await _find_skill_similar_templates(query, db)
        if cluster and cluster.get("status") == "collecting":
            message = "Belum ada role ini, tapi kami sedang mengumpulkan demand!"
        elif cluster and cluster.get("status") == "pending_review":
            message = "Role ini sedang dalam review admin. Nantikan ya!"
        elif cluster and cluster.get("status") == "auto_created":
            message = "Role ini baru saja otomatis dibuat!"
        elif cluster and cluster.get("status") == "approved":
            message = "Role ini sudah tersedia!"
        elif not cluster:
            message = "Belum ada role ini, tapi kami sudah catat demand kamu!"

    return {
        "results": templates,
        "suggestions": suggestions,
        "cluster_id": str(cluster_id) if cluster_id else None,
        "cluster_status": cluster.get("status") if cluster else None,
        "cluster_count": cluster.get("query_count", 0) if cluster else 0,
        "message": message,
    }


# ── Find or create cluster ──────────────────────────────────────────
async def _find_or_create_cluster(
    query: str,
    embedding_str: str,
    fingerprint: str,
    db: AsyncSession,
) -> str | None:
    """Find existing cluster or create new. Returns cluster_id."""
    try:
        # Find closest cluster
        result = await db.execute(sa_text("""
            SELECT id, 1 - (centroid_embedding <=> CAST(:emb AS vector)) AS similarity
            FROM search_clusters
            WHERE status NOT IN ('rejected')
            ORDER BY centroid_embedding <=> CAST(:emb AS vector)
            LIMIT 1
        """), {"emb": embedding_str})
        row = result.first()

        cluster_id = None
        is_new_cluster = False

        if row and row[1] >= SIMILARITY_THRESHOLD:
            # Match found — assign to existing cluster
            cluster_id = str(row[0])
        else:
            # No match — create new cluster
            cluster_id = str(uuid4())
            is_new_cluster = True
            await db.execute(sa_text("""
                INSERT INTO search_clusters (id, representative_query, centroid_embedding, query_count, unique_users, status, created_at, updated_at)
                VALUES (CAST(:id AS uuid), :query, CAST(:emb AS vector), 1, 1, 'collecting', now(), now())
            """), {"id": cluster_id, "query": query, "emb": embedding_str})

        # Log the search query
        await db.execute(sa_text("""
            INSERT INTO search_queries (id, cluster_id, query, query_embedding, user_fingerprint, created_at)
            VALUES (CAST(:id AS uuid), CAST(:cid AS uuid), :query, CAST(:emb AS vector), :fp, now())
        """), {
            "id": str(uuid4()),
            "cid": cluster_id,
            "query": query,
            "emb": embedding_str,
            "fp": fingerprint,
        })

        # Increment counters (only if not new cluster)
        if not is_new_cluster:
            await db.execute(sa_text("""
                UPDATE search_clusters
                SET query_count = query_count + 1,
                    updated_at = now()
                WHERE id = CAST(:id AS uuid)
            """), {"id": cluster_id})

            # Recompute unique users after inserting query (dedup by fingerprint)
            await db.execute(sa_text("""
                UPDATE search_clusters
                SET unique_users = (
                    SELECT COUNT(DISTINCT user_fingerprint)
                    FROM search_queries
                    WHERE cluster_id = CAST(:id AS uuid)
                )
                WHERE id = CAST(:id AS uuid)
            """), {"id": cluster_id})

        await db.commit()

        # Check thresholds
        await _check_thresholds(cluster_id, db)

        return cluster_id

    except Exception as e:
        logger.error("cluster_find_or_create_failed", error=str(e))
        await db.rollback()
        return None


# ── Check thresholds ─────────────────────────────────────────────────
async def _check_thresholds(cluster_id: str, db: AsyncSession):
    """Check if cluster hit min/max thresholds and update status."""
    result = await db.execute(sa_text("""
        SELECT query_count, unique_users, status FROM search_clusters WHERE id = CAST(:id AS uuid)
    """), {"id": cluster_id})
    row = result.first()
    if not row:
        return

    count, unique, status = row

    if status == "collecting" and unique >= SEARCH_MIN_THRESHOLD:
        await db.execute(sa_text("""
            UPDATE search_clusters SET status = 'pending_review', updated_at = now()
            WHERE id = CAST(:id AS uuid)
        """), {"id": cluster_id})
        await db.commit()
        logger.info("cluster_hit_min_threshold", cluster_id=cluster_id, unique_users=unique)
        status = "pending_review"

    if status in ("pending_review", "collecting") and unique >= SEARCH_MAX_THRESHOLD:
        # Auto-create role
        await db.execute(sa_text("""
            UPDATE search_clusters SET status = 'auto_created', updated_at = now()
            WHERE id = CAST(:id AS uuid)
        """), {"id": cluster_id})
        await db.commit()
        logger.info("cluster_hit_max_threshold", cluster_id=cluster_id, unique_users=unique)
        await auto_generate_role(cluster_id, db)


# ── Match existing templates ─────────────────────────────────────────
async def _match_templates(query: str, db: AsyncSession) -> list[dict]:
    """Find templates whose name/specialty/slug text matches the query."""
    q = query.lower().strip()
    tokens = [t for t in re.split(r"\W+", q) if len(t) >= 2]

    result = await db.execute(sa_text("""
        SELECT id, slug, name, specialty, avatar_emoji, price_monthly_idr, is_active
        FROM staff_templates WHERE is_active = true
    """))
    rows = result.fetchall()

    templates = []
    for r in rows:
        haystack = f"{r[1]} {r[2]} {r[3]}".lower()
        score = 0
        for token in tokens:
            if token in haystack:
                score += 1
        # also match common aliases
        if any(alias in q for alias in ["hr", "rekrut", "karyawan"]) and "hr" in haystack:
            score += 3
        if any(alias in q for alias in ["cs", "customer", "pelanggan", "support"]):
            if "customer" in haystack or "cs" in haystack:
                score += 3
        if any(alias in q for alias in ["uang", "keuangan", "akunting", "akuntansi", "kas"]):
            if "akuntansi" in haystack or "keuangan" in haystack:
                score += 3
        if any(alias in q for alias in ["sales", "jual", "closing", "lead"]):
            if "sales" in haystack:
                score += 3
        if any(alias in q for alias in ["pa", "assistant", "asisten", "jadwal"]):
            if "assistant" in haystack or "personal" in haystack:
                score += 2

        if score > 0:
            templates.append({
                "id": str(r[0]),
                "slug": r[1],
                "name": r[2],
                "specialty": r[3],
                "avatar_emoji": r[4],
                "price_monthly_idr": r[5],
                "score": score,
            })

    return sorted(templates, key=lambda x: x["score"], reverse=True)[:5]


# ── Skill-similar suggestion ──────────────────────────────────────

# Map keywords to broad skill categories
_SKILL_CATEGORIES = {
    "admin_inventory": [
        "admin", "inventaris", "stok", "stock", "gudang", "catalog", "katalog",
        "toko", "warung", "toserba", "sembako", "bangunan", "baju", "fashion",
        "material", "perlengkapan", "perabot", "elektronik", "apotek", "farmasi",
        "toko bangunan", "toko sembako", "toko baju", "kelontong", "minimarket",
    ],
    "cs_support": [
        "cs", "customer", "support", "layanan", "keluhan", "komplain", "bantuan",
        "pelanggan", "helpdesk", "service", "purna jual",
    ],
    "sales_marketing": [
        "sales", "jual", "marketing", "promosi", "closing", "lead", "prospecting",
        "penjualan", "omzet", "target", "roi",
    ],
    "finance_accounting": [
        "keuangan", "akuntansi", "kas", "pembukuan", "invoice", "tagihan",
        "hutang", "piutang", "pajak", "laporan keuangan", "akunting",
    ],
    "pa_scheduler": [
        "pa", "assistant", "asisten", "jadwal", "agenda", "meeting", "reminder",
        "sekretaris", "appointments", "kalender",
    ],
    "hr_recruitment": [
        "hr", "rekrutmen", "karyawan", "pegawai", "payroll", "gaji", "cuti",
        "absensi", "training", "onboarding",
    ],
}


def _detect_skill_category(query: str) -> str | None:
    """Detect which skill category a query belongs to."""
    q = query.lower()
    best_cat = None
    best_hits = 0
    for cat, keywords in _SKILL_CATEGORIES.items():
        hits = sum(1 for kw in keywords if kw in q)
        if hits > best_hits:
            best_hits = hits
            best_cat = cat
    return best_cat if best_hits > 0 else None


async def _find_skill_similar_templates(query: str, db: AsyncSession) -> list[dict]:
    """Find templates whose skill category matches the query's detected category."""
    category = _detect_skill_category(query)
    if not category:
        # Fallback: return all active templates (limited) as generic suggestions
        result = await db.execute(sa_text("""
            SELECT id, slug, name, specialty, avatar_emoji, price_monthly_idr
            FROM staff_templates WHERE is_active = true
            ORDER BY name LIMIT 3
        """))
        rows = result.fetchall()
        return [{"id": str(r[0]), "slug": r[1], "name": r[2], "specialty": r[3],
                 "avatar_emoji": r[4], "price_monthly_idr": r[5],
                 "match_reason": "role serupa"} for r in rows]

    # Map category to keywords that should appear in template specialty/name
    _CATEGORY_SPECIALTY_MAP = {
        "admin_inventory": ["admin", "inventaris", "toko", "gudang", "asisten", "pa", "personal assistant", "sekretaris"],
        "cs_support": ["customer", "cs", "support", "layanan", "service"],
        "sales_marketing": ["sales", "marketing", "jual"],
        "finance_accounting": ["akuntansi", "keuangan", "kas", "finance"],
        "pa_scheduler": ["assistant", "pa", "asisten", "sekretaris", "jadwal"],
        "hr_recruitment": ["hr", "rekrutmen", "karyawan"],
    }

    match_keywords = _CATEGORY_SPECIALTY_MAP.get(category, [])
    result = await db.execute(sa_text("""
        SELECT id, slug, name, specialty, avatar_emoji, price_monthly_idr
        FROM staff_templates WHERE is_active = true
    """))
    rows = result.fetchall()

    scored = []
    for r in rows:
        haystack = f"{r[2]} {r[3]} {r[1]}".lower()
        score = sum(1 for kw in match_keywords if kw in haystack)
        if score > 0:
            scored.append({
                "id": str(r[0]), "slug": r[1], "name": r[2], "specialty": r[3],
                "avatar_emoji": r[4], "price_monthly_idr": r[5],
                "match_reason": "kemampuan mirip",
            })

    return sorted(scored, key=lambda x: x.get("match_reason", "") == "kemampuan mirip", reverse=False)[:3]


# ── Get cluster info ─────────────────────────────────────────────────
async def _get_cluster(cluster_id: str, db: AsyncSession) -> dict | None:
    result = await db.execute(sa_text("""
        SELECT id, representative_query, query_count, unique_users, status,
               suggested_slug, suggested_name, suggested_specialty,
               generated_prompt, created_template_id
        FROM search_clusters WHERE id = CAST(:id AS uuid)
    """), {"id": cluster_id})
    row = result.first()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "representative_query": row[1],
        "query_count": row[2],
        "unique_users": row[3],
        "status": row[4],
        "suggested_slug": row[5],
        "suggested_name": row[6],
        "suggested_specialty": row[7],
        "generated_prompt": row[8],
        "created_template_id": str(row[9]) if row[9] else None,
    }


# ── Auto-generate role ───────────────────────────────────────────────
async def auto_generate_role(cluster_id: str, db: AsyncSession) -> dict | None:
    """Use LLM to generate a role from cluster data and save to staff_templates."""
    # Get cluster info + sample queries
    cluster_result = await db.execute(sa_text("""
        SELECT representative_query, query_count, unique_users
        FROM search_clusters WHERE id = CAST(:id AS uuid)
    """), {"id": cluster_id})
    cluster = cluster_result.first()
    if not cluster:
        return None

    samples_result = await db.execute(sa_text("""
        SELECT DISTINCT query FROM search_queries
        WHERE cluster_id = CAST(:id AS uuid)
        LIMIT 10
    """), {"id": cluster_id})
    samples = [r[0] for r in samples_result.fetchall()]

    prompt = f"""Kamu adalah AI yang membuat profil staff virtual baru.
Berdasarkan data search query user, buatkan profil staff AI baru.

Search queries: {json.dumps(samples)}
Jumlah unique user: {cluster[2]}

Respond ONLY with valid JSON (no markdown):
{{
    "slug": "contoh-asisten-toko-bangunan",
    "name": "Kak Bima",
    "specialty": "Asisten Toko Bangunan",
    "avatar_emoji": "🏗️",
    "price_monthly_idr": 89000,
    "base_prompt": "Role:\\nKamu adalah..."
}}

base_prompt harus mengikuti framework:
- Role (identitas)
- Objective (tujuan)
- Scope (cakupan tugas)
- Rules (aturan perilaku, 5+ rules)
- Output style (gaya respons)
- Verification (cara ngecek sebelum jawab)
- Fallback (kalau tidak tahu)

Gunakan bahasa Indonesia. Name harus nama Indonesia (Mbak/Mas/Kak + nama)."""

    try:
        response = await call_llm([{"role": "user", "content": prompt}])

        # Clean response — strip markdown code block if present
        clean = response.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()

        data = json.loads(clean)

        slug = data.get("slug", slugify(cluster[0]))
        name = data.get("name", "Staff AI")
        specialty = data.get("specialty", cluster[0])
        emoji = data.get("avatar_emoji", "🤖")
        price = data.get("price_monthly_idr", 89000)
        base_prompt = data.get("base_prompt", "")

        # Insert into staff_templates
        template_id = str(uuid4())
        await db.execute(sa_text("""
            INSERT INTO staff_templates (id, slug, name, specialty, base_prompt, avatar_emoji, price_monthly_idr, is_active)
            VALUES (CAST(:id AS uuid), :slug, :name, :specialty, :prompt, :emoji, :price, true)
            ON CONFLICT (slug) DO NOTHING
        """), {
            "id": template_id,
            "slug": slug,
            "name": name,
            "specialty": specialty,
            "prompt": base_prompt,
            "emoji": emoji,
            "price": price,
        })

        # Update cluster
        await db.execute(sa_text("""
            UPDATE search_clusters
            SET suggested_slug = :slug, suggested_name = :name,
                suggested_specialty = :specialty, generated_prompt = :prompt,
                created_template_id = CAST(:tid AS uuid),
                status = 'auto_created', updated_at = now()
            WHERE id = CAST(:cid AS uuid)
        """), {
            "slug": slug, "name": name, "specialty": specialty,
            "prompt": base_prompt, "tid": template_id, "cid": cluster_id,
        })

        await db.commit()
        logger.info("auto_role_created", cluster_id=cluster_id, slug=slug, name=name)

        return {
            "template_id": template_id,
            "slug": slug,
            "name": name,
            "specialty": specialty,
        }

    except Exception as e:
        logger.error("auto_role_generation_failed", cluster_id=cluster_id, error=str(e))
        await db.rollback()
        return None


# ── Admin: Get role requests ─────────────────────────────────────────
async def get_role_requests(db: AsyncSession) -> list[dict]:
    """Get all clusters that hit min threshold (pending_review or auto_created)."""
    result = await db.execute(sa_text("""
        SELECT c.id, c.representative_query, c.query_count, c.unique_users,
               c.status, c.suggested_slug, c.suggested_name,
               c.suggested_specialty, c.generated_prompt, c.created_template_id,
               c.created_at, c.updated_at
        FROM search_clusters c
        WHERE c.status IN ('pending_review', 'auto_created', 'approved')
        ORDER BY c.unique_users DESC, c.query_count DESC
    """))
    rows = result.fetchall()

    requests = []
    for r in rows:
        # Get sample queries
        samples = await db.execute(sa_text("""
            SELECT DISTINCT query FROM search_queries
            WHERE cluster_id = CAST(:id AS uuid) LIMIT 10
        """), {"id": str(r[0])})
        sample_queries = [s[0] for s in samples.fetchall()]

        requests.append({
            "cluster_id": str(r[0]),
            "representative_query": r[1],
            "query_count": r[2],
            "unique_users": r[3],
            "status": r[4],
            "suggested_slug": r[5],
            "suggested_name": r[6],
            "suggested_specialty": r[7],
            "generated_prompt": r[8],
            "created_template_id": str(r[9]) if r[9] else None,
            "created_at": str(r[10]) if r[10] else None,
            "updated_at": str(r[11]) if r[11] else None,
            "sample_queries": sample_queries,
        })

    return requests


# ── Admin: Generate draft for a cluster ──────────────────────────────
async def generate_draft(cluster_id: str, db: AsyncSession) -> dict | None:
    """Admin triggers draft generation for a pending cluster."""
    return await auto_generate_role(cluster_id, db)


# ── Admin: Approve and publish ───────────────────────────────────────
async def approve_role_request(
    cluster_id: str,
    overrides: dict,
    db: AsyncSession,
) -> dict | None:
    """Admin approves + publishes a role. Can override name/prompt/etc."""
    # Check if template already exists (auto_created)
    result = await db.execute(sa_text("""
        SELECT created_template_id, suggested_slug FROM search_clusters WHERE id = CAST(:id AS uuid)
    """), {"id": cluster_id})
    row = result.first()
    if not row:
        return None

    template_id = row[0]
    slug = overrides.get("slug", row[1])

    if template_id:
        # Update existing template with overrides
        await db.execute(sa_text("""
            UPDATE staff_templates
            SET name = :name, specialty = :specialty, base_prompt = :prompt,
                avatar_emoji = :emoji, price_monthly_idr = :price, is_active = true
            WHERE id = CAST(:tid AS uuid)
        """), {
            "name": overrides.get("name", ""),
            "specialty": overrides.get("specialty", ""),
            "prompt": overrides.get("base_prompt", ""),
            "emoji": overrides.get("avatar_emoji", "🤖"),
            "price": overrides.get("price_monthly_idr", 89000),
            "tid": str(template_id),
        })
    else:
        # Create new template
        template_id = str(uuid4())
        await db.execute(sa_text("""
            INSERT INTO staff_templates (id, slug, name, specialty, base_prompt, avatar_emoji, price_monthly_idr, is_active)
            VALUES (CAST(:id AS uuid), :slug, :name, :specialty, :prompt, :emoji, :price, true)
        """), {
            "id": template_id,
            "slug": slug,
            "name": overrides.get("name", ""),
            "specialty": overrides.get("specialty", ""),
            "prompt": overrides.get("base_prompt", ""),
            "emoji": overrides.get("avatar_emoji", "🤖"),
            "price": overrides.get("price_monthly_idr", 89000),
        })

    # Update cluster
    await db.execute(sa_text("""
        UPDATE search_clusters
        SET status = 'approved', created_template_id = CAST(:tid AS uuid),
            suggested_name = :name, suggested_specialty = :specialty,
            generated_prompt = :prompt, updated_at = now()
        WHERE id = CAST(:cid AS uuid)
    """), {
        "tid": template_id,
        "name": overrides.get("name", ""),
        "specialty": overrides.get("specialty", ""),
        "prompt": overrides.get("base_prompt", ""),
        "cid": cluster_id,
    })

    await db.commit()
    return {"template_id": template_id, "slug": slug}


# ── Admin: Reject ────────────────────────────────────────────────────
async def reject_role_request(cluster_id: str, db: AsyncSession) -> bool:
    await db.execute(sa_text("""
        UPDATE search_clusters SET status = 'rejected', updated_at = now()
        WHERE id = CAST(:id AS uuid)
    """), {"id": cluster_id})
    await db.commit()
    return True
