export const adminApi = {
  getStats: () => fetch('/api/admin/system/stats').then(r => { if (!r.ok) throw new Error('Auth required'); return r.json(); }),
  getRentals: () => fetch('/api/admin/rentals').then(r => { if (!r.ok) throw new Error('Auth required'); return r.json(); }),
  getRental: (id: string) => fetch(`/api/admin/rentals/${id}`).then(r => { if (!r.ok) throw new Error('Auth required'); return r.json(); }),
  updateTraits: (id: string, traits: any) => fetch(`/api/admin/rentals/${id}/traits`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(traits)}).then(r => r.json()),
  updateStatus: (id: string, status: string) => fetch(`/api/admin/rentals/${id}/status`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status})}).then(r => r.json()),
  getTemplates: () => fetch('/api/admin/templates').then(r => { if (!r.ok) throw new Error('Auth required'); return r.json(); }),
  updateTemplate: (id: string, data: any) => fetch(`/api/admin/templates/${id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}).then(r => r.json()),
  getMemory: (rentalId: string) => fetch(`/api/admin/memory/${rentalId}`).then(r => r.json()),
  deleteMemory: (id: string) => fetch(`/api/admin/memory/${id}`, {method:'DELETE'}),
  getKnowledge: (rentalId: string) => fetch(`/api/admin/knowledge/${rentalId}`).then(r => r.json()),
  addKnowledge: (rentalId: string, data: any) => fetch(`/api/admin/knowledge/${rentalId}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}).then(r => r.json()),
  approveKnowledge: (id: string, status: string) => fetch(`/api/admin/knowledge/${id}/status`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status})}).then(r => r.json()),
  deleteKnowledge: (id: string) => fetch(`/api/admin/knowledge/${id}`, {method:'DELETE'}),
  // WAHA
  wahaSessions: () => fetch('/api/admin/waha/sessions').then(r => { if (!r.ok) throw new Error('Auth required'); return r.json(); }),
  wahaStart: (name: string) => fetch(`/api/admin/waha/sessions/${name}/start`, {method:'POST'}).then(r => r.json()),
  wahaStop: (name: string) => fetch(`/api/admin/waha/sessions/${name}/stop`, {method:'POST'}).then(r => r.json()),
  wahaLogout: (name: string) => fetch(`/api/admin/waha/sessions/${name}/logout`, {method:'POST'}).then(r => r.json()),
  wahaQr: (name: string) => fetch(`/api/admin/waha/sessions/${name}/qr`).then(r => r.json()),
  wahaRequestCode: (name: string, phone: string) => fetch(`/api/admin/waha/sessions/${name}/request-code`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({phone})}).then(r => r.json()),
  wahaDelete: (name: string) => fetch(`/api/admin/waha/sessions/${name}`, {method:'DELETE'}).then(r => r.json()),
  // Messages
  getMessages: (rentalId: string) => fetch(`/api/admin/rentals/${rentalId}/messages`).then(r => { if (!r.ok) throw new Error('Failed'); return r.json(); }),
  // Reminders
  getReminders: (rentalId: string) => fetch(`/api/admin/rentals/${rentalId}/reminders`).then(r => { if (!r.ok) throw new Error('Failed'); return r.json(); }),
  deleteReminder: (reminderId: string) => fetch(`/api/admin/reminders/${reminderId}`, {method:'DELETE'}).then(r => { if (!r.ok) throw new Error('Failed'); return r.json(); }),
  // Role Requests (Demand-Driven)
  getRoleRequests: () => fetch('/api/admin/role-requests').then(r => { if (!r.ok) throw new Error('Failed'); return r.json(); }),
  generateRoleDraft: (clusterId: string) => fetch(`/api/admin/role-requests/${clusterId}/generate`, {method:'POST'}).then(r => { if (!r.ok) throw new Error('Failed'); return r.json(); }),
  approveRoleRequest: (clusterId: string) => fetch(`/api/admin/role-requests/${clusterId}/approve`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({})}).then(r => { if (!r.ok) throw new Error('Failed'); return r.json(); }),
  rejectRoleRequest: (clusterId: string) => fetch(`/api/admin/role-requests/${clusterId}/reject`, {method:'DELETE'}).then(r => { if (!r.ok) throw new Error('Failed'); return r.json(); }),
};
