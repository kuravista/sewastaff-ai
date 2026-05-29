-- Finance Ledger Phase 2: financial_transactions table
-- SewaStaff AI Backend

BEGIN;

CREATE TABLE IF NOT EXISTS financial_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rental_id UUID NOT NULL REFERENCES rental_instances(id) ON DELETE CASCADE,
    group_id TEXT NOT NULL,
    sender_id TEXT,
    tx_type TEXT NOT NULL,
    amount_idr INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'IDR',
    category TEXT,
    merchant TEXT,
    description TEXT NOT NULL,
    transaction_date TIMESTAMPTZ NOT NULL,
    source TEXT,
    image_url TEXT,
    ocr_text TEXT,
    confidence FLOAT NOT NULL DEFAULT 0.7,
    status TEXT NOT NULL DEFAULT 'confirmed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_financial_transactions_type
        CHECK (tx_type IN ('income', 'expense', 'transfer', 'adjustment')),
    CONSTRAINT ck_financial_transactions_status
        CHECK (status IN ('confirmed', 'pending', 'rejected'))
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_finance_rental_group_date
    ON financial_transactions (rental_id, group_id, transaction_date DESC);

CREATE INDEX IF NOT EXISTS idx_finance_type_date
    ON financial_transactions (tx_type, transaction_date DESC);

CREATE INDEX IF NOT EXISTS idx_finance_category
    ON financial_transactions (rental_id, group_id, category)
    WHERE category IS NOT NULL;

COMMIT;
