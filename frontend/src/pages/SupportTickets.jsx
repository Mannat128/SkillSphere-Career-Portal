import React, { useEffect, useState } from 'react';
import {
  MessageCircle,
  Plus,
  Send,
  Paperclip,
  RefreshCw,
  Search,
  X,
  FileText,
  ShieldCheck,
  Clock,
  UserCheck,
  AlertTriangle,
} from 'lucide-react';
import api from '../services/api';

const STATUSES = ['OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'];

const CATEGORIES = [
  'ACCOUNT',
  'JOB_APPLICATION',
  'ASSESSMENT',
  'TECHNICAL',
  'PAYMENT',
  'OTHER',
];

const PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'];

export default function SupportTickets() {
  const user = JSON.parse(
    localStorage.getItem('skillsphere_user') || '{}'
  );

  const isAdmin =
    String(user.role || '').toUpperCase() === 'ADMIN';

  const [tickets, setTickets] = useState([]);
  const [selected, setSelected] = useState(null);
  const [admins, setAdmins] = useState([]);

  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [updating, setUpdating] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [message, setMessage] = useState('');
  const [files, setFiles] = useState([]);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [assignmentValue, setAssignmentValue] = useState('');
  const [priorityValue, setPriorityValue] = useState('MEDIUM');

  const [form, setForm] = useState({
    subject: '',
    description: '',
    category: 'TECHNICAL',
    priority: 'MEDIUM',
    files: [],
  });

  const statusColor = (status) => ({
    OPEN: '#2563eb',
    IN_PROGRESS: '#d97706',
    RESOLVED: '#059669',
    CLOSED: '#64748b',
    LOW: '#64748b',
    MEDIUM: '#2563eb',
    HIGH: '#d97706',
    URGENT: '#dc2626',
  }[status] || '#64748b');

  const styles = {
    page: {
      padding: '28px',
      color: 'var(--text-primary, #20251f)',
      minHeight: '100vh',
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 16,
      flexWrap: 'wrap',
      marginBottom: 24,
    },
    button: {
      border: 0,
      borderRadius: 10,
      padding: '11px 16px',
      background: '#b7f34a',
      color: '#17210d',
      fontWeight: 700,
      cursor: 'pointer',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
    },
    panel: {
      background: 'var(--card-bg, #fff)',
      border: '1px solid var(--border-color, #e5e7eb)',
      borderRadius: 16,
      padding: 20,
    },
    input: {
      width: '100%',
      padding: 12,
      borderRadius: 9,
      border: '1px solid #d8ddd3',
      marginTop: 7,
      marginBottom: 14,
      boxSizing: 'border-box',
      background: 'var(--input-bg, #fff)',
      color: 'inherit',
    },
    muted: {
      color: '#788174',
      fontSize: 13,
    },
    badge: (status) => ({
      color: statusColor(status),
      background: `${statusColor(status)}18`,
      borderRadius: 20,
      padding: '5px 10px',
      fontSize: 11,
      fontWeight: 700,
      whiteSpace: 'nowrap',
    }),
  };

  // ------------------------------------------------------
  // LOAD TICKETS
  // ------------------------------------------------------

  const loadTickets = async () => {
    try {
      setLoading(true);
      setError('');

      const endpoint = isAdmin
        ? '/support-tickets/admin/all'
        : '/support-tickets';

      const response = await api.get(endpoint);
      const data = response.data || [];

      setTickets(data);

      if (selected) {
        const updated = data.find(
          (ticket) => ticket.id === selected.id
        );

        if (updated) {
          setSelected((previous) => ({
            ...previous,
            ...updated,
          }));
        }
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load tickets.'
      );
    } finally {
      setLoading(false);
    }
  };

  // ------------------------------------------------------
  // LOAD ASSIGNABLE ADMIN USERS
  // ------------------------------------------------------

  const loadAdmins = async () => {
    if (!isAdmin) return;

    try {
      const response = await api.get(
        '/support-tickets/admin/assignable-admins'
      );

      setAdmins(response.data || []);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load Admin users.'
      );
    }
  };

  // ------------------------------------------------------
  // LOAD TICKET DETAIL
  // ------------------------------------------------------

  const loadTicket = async (id) => {
    try {
      setError('');

      const response = await api.get(
        `/support-tickets/${id}`
      );

      const ticket = response.data;

      setSelected(ticket);

      setAssignmentValue(
        ticket.assigned_admin_id
          ? String(ticket.assigned_admin_id)
          : ''
      );

      setPriorityValue(ticket.priority || 'MEDIUM');
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to open ticket.'
      );
    }
  };

  useEffect(() => {
    loadTickets();

    if (isAdmin) {
      loadAdmins();
    }
  }, []);

  // ------------------------------------------------------
  // CREATE TICKET
  // ------------------------------------------------------

  const createTicket = async (event) => {
    event.preventDefault();

    try {
      setSending(true);
      setError('');
      setSuccess('');

      const data = new FormData();

      data.append('subject', form.subject);
      data.append('description', form.description);
      data.append('category', form.category);
      data.append('priority', form.priority);

      form.files.forEach((file) => {
        data.append('files', file);
      });

      await api.post('/support-tickets', data);

      setShowCreate(false);

      setForm({
        subject: '',
        description: '',
        category: 'TECHNICAL',
        priority: 'MEDIUM',
        files: [],
      });

      setSuccess('Support ticket created successfully.');

      await loadTickets();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Ticket creation failed.'
      );
    } finally {
      setSending(false);
    }
  };

  // ------------------------------------------------------
  // SEND TICKET MESSAGE
  // ------------------------------------------------------

  const sendMessage = async (event) => {
    event.preventDefault();

    if (!message.trim() && files.length === 0) {
      return;
    }

    try {
      setSending(true);
      setError('');
      setSuccess('');

      const data = new FormData();

      data.append('message', message);

      files.forEach((file) => {
        data.append('files', file);
      });

      await api.post(
        `/support-tickets/${selected.id}/messages`,
        data
      );

      setMessage('');
      setFiles([]);

      await loadTicket(selected.id);
      await loadTickets();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Message could not be sent.'
      );
    } finally {
      setSending(false);
    }
  };

  // ------------------------------------------------------
  // ADMIN: UPDATE STATUS
  // ------------------------------------------------------

  const updateStatus = async (status) => {
    if (!selected) return;

    try {
      setUpdating(true);
      setError('');
      setSuccess('');

      await api.patch(
        `/support-tickets/admin/${selected.id}/status`,
        null,
        {
          params: {
            new_status: status,
          },
        }
      );

      setSuccess('Ticket status updated successfully.');

      await loadTicket(selected.id);
      await loadTickets();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Status update failed.'
      );
    } finally {
      setUpdating(false);
    }
  };

  // ------------------------------------------------------
  // ADMIN: ASSIGN / REASSIGN / UNASSIGN
  // ------------------------------------------------------

  const updateAssignment = async () => {
    if (!selected) return;

    try {
      setUpdating(true);
      setError('');
      setSuccess('');

      await api.patch(
        `/support-tickets/admin/${selected.id}/assignment`,
        {
          admin_id: assignmentValue
            ? Number(assignmentValue)
            : null,
        }
      );

      setSuccess(
        assignmentValue
          ? 'Ticket assignment updated successfully.'
          : 'Ticket unassigned successfully.'
      );

      await loadTicket(selected.id);
      await loadTickets();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Ticket assignment update failed.'
      );
    } finally {
      setUpdating(false);
    }
  };

  // ------------------------------------------------------
  // ADMIN: CHANGE PRIORITY
  // ------------------------------------------------------

  const updatePriority = async () => {
    if (!selected) return;

    try {
      setUpdating(true);
      setError('');
      setSuccess('');

      await api.patch(
        `/support-tickets/admin/${selected.id}/priority`,
        {
          priority: priorityValue,
        }
      );

      setSuccess('Ticket priority updated successfully.');

      await loadTicket(selected.id);
      await loadTickets();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Priority update failed.'
      );
    } finally {
      setUpdating(false);
    }
  };

  // ------------------------------------------------------
  // DOWNLOAD ATTACHMENT
  // ------------------------------------------------------

  const downloadAttachment = async (attachment) => {
    try {
      const response = await api.get(
        `/support-tickets/${selected.id}/attachments/${attachment.id}`,
        {
          responseType: 'blob',
        }
      );

      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');

      link.href = url;
      link.download = attachment.original_filename;
      link.click();

      URL.revokeObjectURL(url);
    } catch {
      setError('Unable to download attachment.');
    }
  };

  // ------------------------------------------------------
  // HELPERS
  // ------------------------------------------------------

  const filteredTickets = tickets.filter((ticket) =>
    `${ticket.ticket_number} ${ticket.subject}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const getAdminName = (adminId) => {
    const admin = admins.find(
      (item) => item.id === adminId
    );

    if (!admin) {
      return adminId
        ? `Admin #${adminId}`
        : 'Unassigned';
    }

    return `${admin.full_name} (${admin.email})`;
  };

  // ------------------------------------------------------
  // PAGE UI
  // ------------------------------------------------------

  return (
    <div style={styles.page}>
      {/* PAGE HEADER */}
      <div style={styles.header}>
        <div>
          <h1 style={{ margin: 0, fontSize: 27 }}>
            Support Center
          </h1>

          <p style={styles.muted}>
            {isAdmin
              ? 'Manage platform support requests, assignments, priorities and conversations.'
              : 'Create a support request and chat with our support team.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            style={styles.button}
            onClick={() => {
              loadTickets();

              if (isAdmin) {
                loadAdmins();
              }
            }}
          >
            <RefreshCw size={16} />
            Refresh
          </button>

          {!isAdmin && (
            <button
              style={styles.button}
              onClick={() => setShowCreate(true)}
            >
              <Plus size={17} />
              New Ticket
            </button>
          )}
        </div>
      </div>

      {/* ERROR MESSAGE */}
      {error && (
        <div
          style={{
            background: '#fee2e2',
            color: '#991b1b',
            padding: 12,
            borderRadius: 9,
            marginBottom: 16,
          }}
        >
          {error}

          <button
            onClick={() => setError('')}
            style={{
              float: 'right',
              border: 0,
              background: 'none',
              cursor: 'pointer',
            }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* SUCCESS MESSAGE */}
      {success && (
        <div
          style={{
            background: '#dcfce7',
            color: '#166534',
            padding: 12,
            borderRadius: 9,
            marginBottom: 16,
          }}
        >
          {success}
        </div>
      )}

      {/* MAIN LAYOUT */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns:
            'minmax(260px, 0.8fr) minmax(0, 1.5fr)',
          gap: 18,
        }}
      >
        {/* TICKET LIST */}
        <section style={styles.panel}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 16,
            }}
          >
            <MessageCircle size={19} />

            <h3 style={{ margin: 0 }}>
              Tickets ({tickets.length})
            </h3>
          </div>

          {/* SEARCH */}
          <div style={{ position: 'relative' }}>
            <Search
              size={16}
              style={{
                position: 'absolute',
                top: 18,
                left: 10,
                color: '#89918a',
              }}
            />

            <input
              style={{
                ...styles.input,
                paddingLeft: 34,
              }}
              placeholder="Search tickets..."
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
            />
          </div>

          {/* TICKETS */}
          {loading ? (
            <p style={styles.muted}>
              Loading tickets...
            </p>
          ) : filteredTickets.length === 0 ? (
            <p style={styles.muted}>
              No support tickets found.
            </p>
          ) : (
            filteredTickets.map((ticket) => (
              <button
                key={ticket.id}
                onClick={() => loadTicket(ticket.id)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: 14,
                  marginBottom: 9,
                  borderRadius: 11,
                  border:
                    selected?.id === ticket.id
                      ? '1px solid #9acb39'
                      : '1px solid #e5e9e1',
                  background:
                    selected?.id === ticket.id
                      ? '#b7f34a18'
                      : 'transparent',
                  cursor: 'pointer',
                  color: 'inherit',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 8,
                    flexWrap: 'wrap',
                  }}
                >
                  <b>{ticket.ticket_number}</b>

                  <span style={styles.badge(ticket.status)}>
                    {ticket.status.replace('_', ' ')}
                  </span>
                </div>

                <p
                  style={{
                    margin: '9px 0 5px',
                    fontWeight: 600,
                  }}
                >
                  {ticket.subject}
                </p>

                <span style={styles.muted}>
                  {ticket.category} ·{' '}
                  <span
                    style={{
                      color: statusColor(ticket.priority),
                      fontWeight: 700,
                    }}
                  >
                    {ticket.priority}
                  </span>
                </span>

                {isAdmin && ticket.assigned_admin_id && (
                  <p
                    style={{
                      ...styles.muted,
                      margin: '7px 0 0',
                    }}
                  >
                    Assigned Admin: #{ticket.assigned_admin_id}
                  </p>
                )}
              </button>
            ))
          )}
        </section>

        {/* TICKET DETAILS */}
        <section style={styles.panel}>
          {!selected ? (
            <div
              style={{
                minHeight: 350,
                display: 'grid',
                placeItems: 'center',
                textAlign: 'center',
              }}
            >
              <div>
                <MessageCircle
                  size={38}
                  color="#9aaa8e"
                />

                <h3>Select a ticket</h3>

                <p style={styles.muted}>
                  Choose a ticket to view its conversation.
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* DETAIL HEADER */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                  flexWrap: 'wrap',
                  borderBottom: '1px solid #e5e9e1',
                  paddingBottom: 16,
                }}
              >
                <div>
                  <span style={styles.muted}>
                    {selected.ticket_number}
                  </span>

                  <h2 style={{ margin: '5px 0' }}>
                    {selected.subject}
                  </h2>

                  <span style={styles.badge(selected.status)}>
                    {selected.status.replace('_', ' ')}
                  </span>
                </div>

                {/* ADMIN STATUS CONTROL */}
                {isAdmin && (
                  <select
                    value={selected.status}
                    disabled={updating}
                    onChange={(event) =>
                      updateStatus(event.target.value)
                    }
                    style={{
                      ...styles.input,
                      width: 'auto',
                      alignSelf: 'center',
                    }}
                  >
                    {STATUSES.map((status) => (
                      <option
                        key={status}
                        value={status}
                      >
                        {status.replace('_', ' ')}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* ADMIN MANAGEMENT CONTROLS */}
              {isAdmin && (
                <div
                  style={{
                    marginTop: 16,
                    marginBottom: 16,
                    padding: 16,
                    border: '1px solid #e5e9e1',
                    borderRadius: 12,
                    background: 'var(--card-bg, #fff)',
                  }}
                >
                  <h3
                    style={{
                      margin: '0 0 15px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                    }}
                  >
                    <ShieldCheck size={18} />
                    Admin Ticket Management
                  </h3>

                  {/* ASSIGNMENT */}
                  <label
                    style={{
                      fontWeight: 600,
                      fontSize: 13,
                    }}
                  >
                    <UserCheck
                      size={14}
                      style={{
                        verticalAlign: 'middle',
                        marginRight: 5,
                      }}
                    />
                    Assign Ticket to Admin
                  </label>

                  <select
                    value={assignmentValue}
                    disabled={updating}
                    onChange={(event) =>
                      setAssignmentValue(event.target.value)
                    }
                    style={styles.input}
                  >
                    <option value="">
                      Unassigned
                    </option>

                    {admins.map((admin) => (
                      <option
                        key={admin.id}
                        value={String(admin.id)}
                      >
                        {admin.full_name} — {admin.email}
                      </option>
                    ))}
                  </select>

                  <button
                    type="button"
                    style={{
                      ...styles.button,
                      marginBottom: 18,
                    }}
                    disabled={updating}
                    onClick={updateAssignment}
                  >
                    {updating
                      ? 'Updating...'
                      : 'Save Assignment'}
                  </button>

                  {/* PRIORITY */}
                  <label
                    style={{
                      fontWeight: 600,
                      fontSize: 13,
                      display: 'block',
                    }}
                  >
                    <AlertTriangle
                      size={14}
                      style={{
                        verticalAlign: 'middle',
                        marginRight: 5,
                      }}
                    />
                    Ticket Priority
                  </label>

                  <div
                    style={{
                      display: 'flex',
                      gap: 10,
                      flexWrap: 'wrap',
                      alignItems: 'center',
                    }}
                  >
                    <select
                      value={priorityValue}
                      disabled={updating}
                      onChange={(event) =>
                        setPriorityValue(event.target.value)
                      }
                      style={{
                        ...styles.input,
                        flex: '1 1 180px',
                        marginBottom: 0,
                      }}
                    >
                      {PRIORITIES.map((priority) => (
                        <option
                          key={priority}
                          value={priority}
                        >
                          {priority}
                        </option>
                      ))}
                    </select>

                    <button
                      type="button"
                      style={styles.button}
                      disabled={updating}
                      onClick={updatePriority}
                    >
                      Save Priority
                    </button>
                  </div>
                </div>
              )}

              {/* DESCRIPTION */}
              <div
                style={{
                  background: '#f5f7f2',
                  borderRadius: 10,
                  padding: 13,
                  margin: '16px 0',
                }}
              >
                <p style={{ margin: 0 }}>
                  {selected.description}
                </p>

                <p style={styles.muted}>
                  Category: {selected.category} · Priority:{' '}
                  <span
                    style={{
                      color: statusColor(selected.priority),
                      fontWeight: 700,
                    }}
                  >
                    {selected.priority}
                  </span>
                </p>

                {selected.assigned_admin_id && (
                  <p style={styles.muted}>
                    <UserCheck
                      size={13}
                      style={{ verticalAlign: 'middle' }}
                    />{' '}
                    Assigned Admin:{' '}
                    {getAdminName(selected.assigned_admin_id)}
                  </p>
                )}

                <p style={styles.muted}>
                  <Clock
                    size={13}
                    style={{ verticalAlign: 'middle' }}
                  />{' '}
                  Created:{' '}
                  {selected.created_at
                    ? new Date(
                        selected.created_at
                      ).toLocaleString()
                    : '—'}
                </p>
              </div>

              {/* CONVERSATION */}
              <h3 style={{ fontSize: 16 }}>
                Conversation
              </h3>

              <div
                style={{
                  maxHeight: 340,
                  overflowY: 'auto',
                  padding: '5px 2px',
                }}
              >
                {(selected.messages || []).map((item) => (
                  <div
                    key={item.id}
                    style={{
                      marginBottom: 13,
                      display: 'flex',
                      justifyContent:
                        item.is_admin_reply
                          ? 'flex-start'
                          : 'flex-end',
                    }}
                  >
                    <div
                      style={{
                        maxWidth: '82%',
                        background: item.is_admin_reply
                          ? '#eef2e9'
                          : '#e8f5cf',
                        borderRadius: 12,
                        padding: 12,
                      }}
                    >
                      <b style={{ fontSize: 12 }}>
                        {item.is_admin_reply
                          ? 'Support Team'
                          : 'User'}
                      </b>

                      <p style={{ margin: '6px 0' }}>
                        {item.message}
                      </p>

                      <span style={styles.muted}>
                        {new Date(
                          item.created_at
                        ).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* ATTACHMENTS */}
              {(selected.attachments || []).length > 0 && (
                <>
                  <h4>Attachments</h4>

                  {selected.attachments.map((file) => (
                    <button
                      key={file.id}
                      onClick={() =>
                        downloadAttachment(file)
                      }
                      style={{
                        ...styles.button,
                        margin: '0 8px 8px 0',
                        background: '#edf1e8',
                      }}
                    >
                      <FileText size={15} />
                      {file.original_filename}
                    </button>
                  ))}
                </>
              )}

              {/* MESSAGE FORM */}
              {selected.status !== 'CLOSED' && (
                <form onSubmit={sendMessage}>
                  <textarea
                    style={{
                      ...styles.input,
                      minHeight: 85,
                    }}
                    placeholder="Write your message..."
                    value={message}
                    onChange={(event) =>
                      setMessage(event.target.value)
                    }
                  />

                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 10,
                      flexWrap: 'wrap',
                    }}
                  >
                    <label
                      style={{
                        ...styles.button,
                        background: '#edf1e8',
                      }}
                    >
                      <Paperclip size={16} />
                      Attach files

                      <input
                        hidden
                        type="file"
                        multiple
                        accept=".pdf,.jpg,.jpeg,.png,.webp"
                        onChange={(event) =>
                          setFiles(
                            Array.from(
                              event.target.files || []
                            )
                          )
                        }
                      />
                    </label>

                    <button
                      style={styles.button}
                      disabled={sending}
                      type="submit"
                    >
                      <Send size={16} />
                      {sending
                        ? 'Sending...'
                        : 'Send Message'}
                    </button>
                  </div>

                  {files.length > 0 && (
                    <p style={styles.muted}>
                      Selected: {files.map((file) => file.name).join(', ')}
                    </p>
                  )}
                </form>
              )}
            </>
          )}
        </section>
      </div>

      {/* CREATE TICKET MODAL */}
      {showCreate && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            background: '#0008',
            display: 'grid',
            placeItems: 'center',
            padding: 16,
          }}
        >
          <form
            onSubmit={createTicket}
            style={{
              ...styles.panel,
              width: 'min(520px, 100%)',
              maxHeight: '90vh',
              overflowY: 'auto',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <h2>Create Support Ticket</h2>

              <button
                type="button"
                onClick={() => setShowCreate(false)}
                style={{
                  border: 0,
                  background: 'none',
                  cursor: 'pointer',
                }}
              >
                <X />
              </button>
            </div>

            <label>Subject</label>

            <input
              required
              maxLength={200}
              style={styles.input}
              value={form.subject}
              onChange={(event) =>
                setForm({
                  ...form,
                  subject: event.target.value,
                })
              }
            />

            <label>Description</label>

            <textarea
              required
              style={{
                ...styles.input,
                minHeight: 100,
              }}
              value={form.description}
              onChange={(event) =>
                setForm({
                  ...form,
                  description: event.target.value,
                })
              }
            />

            <label>Category</label>

            <select
              style={styles.input}
              value={form.category}
              onChange={(event) =>
                setForm({
                  ...form,
                  category: event.target.value,
                })
              }
            >
              {CATEGORIES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>

            <label>Priority</label>

            <select
              style={styles.input}
              value={form.priority}
              onChange={(event) =>
                setForm({
                  ...form,
                  priority: event.target.value,
                })
              }
            >
              {PRIORITIES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>

            <label>Attachments</label>

            <input
              type="file"
              multiple
              accept=".pdf,.jpg,.jpeg,.png,.webp"
              style={styles.input}
              onChange={(event) =>
                setForm({
                  ...form,
                  files: Array.from(
                    event.target.files || []
                  ),
                })
              }
            />

            <button
              style={{
                ...styles.button,
                width: '100%',
              }}
              disabled={sending}
            >
              {sending
                ? 'Creating...'
                : 'Submit Ticket'}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}