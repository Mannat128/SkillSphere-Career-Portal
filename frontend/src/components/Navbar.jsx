import React, { useState, useEffect } from 'react';
import { Bell, User as UserIcon, LogOut, CheckCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';

export default function Navbar() {
  const { user, logout } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 20000); // 20s refresh
    return () => clearInterval(interval);
  }, []);

  const fetchNotifications = async () => {
    try {
      const res = await api.get('/notifications');
      setNotifications(res.data.items || []);
      setUnreadCount(res.data.unread_count || 0);
    } catch (e) {
      // silent
    }
  };

  const markAllRead = async () => {
    try {
      await api.put('/notifications/read-all');
      setUnreadCount(0);
      setNotifications(notifications.map(n => ({ ...n, is_read: true })));
    } catch (e) {}
  };

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 32px',
      background: 'var(--color-ivory)',
      backdropFilter: 'blur(8px)',
      borderBottom: '1px solid var(--border-soft)',
      position: 'sticky',
      top: 0,
      zIndex: 40,
    }}>
      <div>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Welcome back,</span>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          {user?.full_name || 'User'}
        </h3>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        {/* Notifications Popover */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              background: '#FFFFFF',
              border: '1px solid var(--border-soft)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            <Bell size={18} color="var(--text-secondary)" />
            {unreadCount > 0 && (
              <span style={{
                position: 'absolute',
                top: '-2px',
                right: '-2px',
                background: 'var(--accent-peach)',
                color: '#0F172A',
                fontSize: '0.7rem',
                fontWeight: 800,
                width: '18px',
                height: '18px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                {unreadCount}
              </span>
            )}
          </button>

          {showDropdown && (
            <div style={{
              position: 'absolute',
              right: 0,
              top: '50px',
              width: '320px',
              background: '#FFFFFF',
              borderRadius: 'var(--radius-lg)',
              border: 'var(--glass-border)',
              boxShadow: 'var(--shadow-lg)',
              padding: '16px',
              zIndex: 100,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Notifications</h4>
                {unreadCount > 0 && (
                  <button onClick={markAllRead} style={{ fontSize: '0.75rem', color: 'var(--primary-powder-blue-dark)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <CheckCheck size={14} /> Mark all read
                  </button>
                )}
              </div>

              <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
                {notifications.length === 0 ? (
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textAlign: 'center', padding: '16px' }}>
                    No notifications yet.
                  </p>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      style={{
                        padding: '10px',
                        borderRadius: 'var(--radius-sm)',
                        background: n.is_read ? 'transparent' : 'var(--surface-subtle)',
                        borderBottom: '1px solid rgba(0,0,0,0.04)',
                        marginBottom: '4px',
                      }}
                    >
                      <p style={{ fontSize: '0.85rem', fontWeight: n.is_read ? 500 : 700 }}>{n.title}</p>
                      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>{n.message}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Profile Pill & Logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: '#FFFFFF',
            padding: '6px 14px',
            borderRadius: '24px',
            border: '1px solid var(--border-soft)',
            boxShadow: 'var(--shadow-sm)'
          }}>
            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              background: 'var(--primary-powder-blue)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '0.8rem',
              color: '#0F172A'
            }}>
              {user?.full_name?.charAt(0) || 'U'}
            </div>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{user?.full_name}</span>
            <span className={`badge ${user?.role === 'ADMIN' ? 'badge-peach' : user?.role === 'RECRUITER' ? 'badge-blue' : 'badge-success'}`} style={{ fontSize: '0.65rem' }}>
              {user?.role}
            </span>
          </div>

          <button
            onClick={logout}
            title="Log out"
            style={{
              padding: '8px',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--danger)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
              background: 'var(--danger-bg)'
            }}
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </header>
  );
}
