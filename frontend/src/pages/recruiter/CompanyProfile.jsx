
import React, { useEffect, useState } from 'react';
import {
  Building2, Globe, MapPin, Mail, Phone,
  BriefcaseBusiness, Pencil, Save, X, RefreshCw,
  Image as ImageIcon
} from 'lucide-react';
import api from '../../services/api';
import '../candidate/dashboard.css';

const EMPTY_FORM = {
  name: '',
  logo_url: '',
  description: '',
  website: '',
  industry: '',
  location: '',
  contact_email: '',
  contact_phone: ''
};

export default function CompanyProfile() {
  const [company, setCompany] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadCompany = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await api.get('/recruiter/company');
      const data = response.data || null;

      setCompany(data);
      setForm({
        name: data?.name || '',
        logo_url: data?.logo_url || '',
        description: data?.description || '',
        website: data?.website || '',
        industry: data?.industry || '',
        location: data?.location || '',
        contact_email: data?.contact_email || '',
        contact_phone: data?.contact_phone || ''
      });
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load company profile.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompany();
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((previous) => ({
      ...previous,
      [name]: value
    }));
  };

  const startEditing = () => {
    setError('');
    setSuccess('');
    setEditing(true);
  };

  const cancelEditing = () => {
    setForm({
      name: company?.name || '',
      logo_url: company?.logo_url || '',
      description: company?.description || '',
      website: company?.website || '',
      industry: company?.industry || '',
      location: company?.location || '',
      contact_email: company?.contact_email || '',
      contact_phone: company?.contact_phone || ''
    });

    setEditing(false);
    setError('');
  };

  const saveCompany = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!form.name.trim()) {
      setError('Company name is required.');
      return;
    }

    setSaving(true);

    const payload = {
      name: form.name.trim(),
      logo_url: form.logo_url.trim() || null,
      description: form.description.trim() || null,
      website: form.website.trim() || null,
      industry: form.industry.trim() || null,
      location: form.location.trim() || null,
      contact_email: form.contact_email.trim() || null,
      contact_phone: form.contact_phone.trim() || null
    };

    try {
      const response = await api.put('/recruiter/company', payload);

      setCompany(response.data);
      setForm({
        name: response.data?.name || '',
        logo_url: response.data?.logo_url || '',
        description: response.data?.description || '',
        website: response.data?.website || '',
        industry: response.data?.industry || '',
        location: response.data?.location || '',
        contact_email: response.data?.contact_email || '',
        contact_phone: response.data?.contact_phone || ''
      });

      setEditing(false);
      setSuccess('Company profile saved successfully.');
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to save company profile.'
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="ss-dashboard">
        <div className="ss-loading">Loading company profile...</div>
      </div>
    );
  }

  return (
    <div className="ss-dashboard">
      <div className="ss-heading">
        <div>
          <span className="ss-eyebrow">COMPANY WORKSPACE</span>
          <h1>Company Profile</h1>
          <p>Manage your organization's public information.</p>
        </div>

        {!editing ? (
          <button className="ss-primary-btn" onClick={startEditing}>
            <Pencil size={15} /> Edit Profile
          </button>
        ) : (
          <button className="pipeline-cancel-btn" onClick={cancelEditing}>
            <X size={15} /> Cancel
          </button>
        )}
      </div>

      {error && <div className="ss-alert">{error}</div>}
      {success && <div className="ss-notice">{success}</div>}

      <div className="ss-card company-profile-card">
        <div className="company-profile-banner">
          <div className="company-logo">
            {form.logo_url ? (
              <img
                src={form.logo_url}
                alt="Company logo"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
            ) : (
              <Building2 size={34} />
            )}
          </div>

          <div className="company-banner-info">
            <span className="ss-eyebrow">ORGANIZATION</span>
            <h2>{company?.name || 'Your Company'}</h2>
            <p>{company?.industry || 'Industry not specified'}</p>
          </div>
        </div>

        {editing ? (
          <form className="company-edit-form" onSubmit={saveCompany}>
            <div className="ss-card-head">
              <div>
                <h3>Edit Company Information</h3>
                <p>Update your company details below.</p>
              </div>
            </div>

            <div className="ss-form-grid">
              <label className="ss-form-full">
                Company Name *
                <input
                  name="name"
                  value={form.name}
                  onChange={handleChange}
                  placeholder="Enter company name"
                  minLength={2}
                  maxLength={200}
                  required
                />
              </label>

              <label className="ss-form-full">
                Company Logo URL
                <input
                  type="url"
                  name="logo_url"
                  value={form.logo_url}
                  onChange={handleChange}
                  placeholder="https://example.com/logo.png"
                />
              </label>

              <label>
                Industry
                <input
                  name="industry"
                  value={form.industry}
                  onChange={handleChange}
                  placeholder="e.g. Information Technology"
                />
              </label>

              <label>
                Location
                <input
                  name="location"
                  value={form.location}
                  onChange={handleChange}
                  placeholder="City, Country"
                />
              </label>

              <label>
                Website
                <input
                  type="url"
                  name="website"
                  value={form.website}
                  onChange={handleChange}
                  placeholder="https://company.com"
                />
              </label>

              <label>
                Contact Email
                <input
                  type="email"
                  name="contact_email"
                  value={form.contact_email}
                  onChange={handleChange}
                  placeholder="hr@company.com"
                />
              </label>

              <label>
                Contact Phone
                <input
                  type="tel"
                  name="contact_phone"
                  value={form.contact_phone}
                  onChange={handleChange}
                  placeholder="Enter contact number"
                />
              </label>

              <label className="ss-form-full">
                Company Description
                <textarea
                  name="description"
                  rows={5}
                  value={form.description}
                  onChange={handleChange}
                  placeholder="Tell candidates about your company..."
                />
              </label>
            </div>

            <div className="company-form-actions">
              <button
                type="button"
                className="pipeline-cancel-btn"
                onClick={cancelEditing}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="ss-primary-btn"
                disabled={saving}
              >
                <Save size={15} />
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        ) : (
          <div className="company-profile-content">
            <div className="company-section-heading">
              <h3>About Company</h3>
              <button
                className="pipeline-icon-btn"
                onClick={loadCompany}
                title="Refresh"
              >
                <RefreshCw size={14} />
              </button>
            </div>

            <p className="company-description">
              {company?.description || 'No company description added yet.'}
            </p>

            <div className="company-details-grid">
              <div className="company-detail">
                <Globe size={17} />
                <div>
                  <small>Website</small>
                  {company?.website ? (
                    <a href={company.website} target="_blank" rel="noopener noreferrer">
                      {company.website}
                    </a>
                  ) : <strong>Not provided</strong>}
                </div>
              </div>

              <div className="company-detail">
                <BriefcaseBusiness size={17} />
                <div>
                  <small>Industry</small>
                  <strong>{company?.industry || 'Not provided'}</strong>
                </div>
              </div>

              <div className="company-detail">
                <MapPin size={17} />
                <div>
                  <small>Location</small>
                  <strong>{company?.location || 'Not provided'}</strong>
                </div>
              </div>

              <div className="company-detail">
                <Mail size={17} />
                <div>
                  <small>Contact Email</small>
                  <strong>{company?.contact_email || 'Not provided'}</strong>
                </div>
              </div>

              <div className="company-detail">
                <Phone size={17} />
                <div>
                  <small>Contact Phone</small>
                  <strong>{company?.contact_phone || 'Not provided'}</strong>
                </div>
              </div>
            </div>

            {!company && (
              <div className="ss-empty company-empty">
                <Building2 size={30} />
                <h3>Company profile not created</h3>
                <p>Add your company information to get started.</p>
                <button className="ss-primary-btn" onClick={startEditing}>
                  Create Company Profile
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
