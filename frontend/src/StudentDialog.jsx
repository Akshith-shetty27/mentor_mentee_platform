import { useEffect, useState } from 'react';
import { ArrowRight, CircleAlert, LoaderCircle, X } from 'lucide-react';
import './student-dialog.css';

export default function StudentDialog({ mode, student, onClose, onSave, loadMentors }) {
  const creating = mode === 'create';
  const restricted = mode === 'restricted';
  const [form, setForm] = useState({
    name: student?.name || '',
    student_code: student?.student_code || '',
    email: student?.email || '',
    department: student?.department || '',
    semester: student?.semester ?? '',
    phone: student?.phone || '',
    mentor_id: '',
  });
  const [mentors, setMentors] = useState([]);
  const [loadingMentors, setLoadingMentors] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!creating) return;
    setLoadingMentors(true);
    loadMentors()
      .then(setMentors)
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoadingMentors(false));
  }, []);

  const update = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
  };

  async function submit(event) {
    event.preventDefault();
    setError('');
    setSaving(true);
    try {
      await onSave({
        ...form,
        semester: form.semester === '' ? undefined : Number(form.semester),
        ...(creating ? { mentor_id: Number(form.mentor_id) } : {}),
      });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !saving) onClose();
    }}>
      <section className="modal student-modal" role="dialog" aria-modal="true" aria-labelledby="student-dialog-title">
        <div className="modal-head">
          <div>
            <span className="eyebrow">MENTORCONNECT WORKSPACE</span>
            <h2 id="student-dialog-title">
              {restricted ? 'Student accounts are admin-managed' : creating ? 'Add student' : 'Edit student details'}
            </h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} disabled={saving} aria-label="Close dialog">
            <X size={19} />
          </button>
        </div>

        {restricted ? (
          <>
            <p className="student-dialog-copy">
              To preserve the current account and assignment permissions, only an administrator can create student
              accounts and assign them to mentors. Ask an administrator to add the student and select your workspace.
            </p>
            <div className="modal-actions">
              <button type="button" className="btn-primary" onClick={onClose}>Got it <ArrowRight size={16} /></button>
            </div>
          </>
        ) : (
          <form onSubmit={submit}>
            {error && <div className="alert-error" role="alert"><CircleAlert size={16} /><span>{error}</span></div>}
            <label>
              Full name
              <input autoFocus required maxLength={120} value={form.name} onChange={update('name')} />
            </label>
            {creating && (
              <label>
                Student ID
                <input required maxLength={40} value={form.student_code} onChange={update('student_code')} />
              </label>
            )}
            <label>
              Email address
              <input type="email" required maxLength={180} value={form.email} onChange={update('email')} />
            </label>
            <div className="form-grid">
              <label>
                Department
                <input required maxLength={100} value={form.department} onChange={update('department')} />
              </label>
              <label>
                Semester {!creating && form.semester === '' && <span className="optional-label">Optional</span>}
                <input
                  type="number"
                  required={creating}
                  min="1"
                  max="12"
                  step="1"
                  value={form.semester}
                  onChange={update('semester')}
                />
              </label>
            </div>
            <label>
              Phone number <span className="optional-label">Optional</span>
              <input type="tel" maxLength={40} value={form.phone} onChange={update('phone')} />
            </label>
            {creating && (
              <label>
                Assign mentor
                <select required value={form.mentor_id} onChange={update('mentor_id')} disabled={loadingMentors || !mentors.length}>
                  <option value="">{loadingMentors ? 'Loading mentors…' : 'Select a mentor'}</option>
                  {mentors.map((mentor) => (
                    <option key={mentor.id} value={mentor.id}>{mentor.name} · {mentor.department}</option>
                  ))}
                </select>
                {!loadingMentors && !mentors.length && !error && (
                  <span className="form-hint">An active mentor is required to create and assign this student.</span>
                )}
              </label>
            )}
            <div className="modal-actions">
              <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
              <button
                className="btn-primary"
                disabled={saving || loadingMentors || (creating && !mentors.length)}
              >
                {saving ? <><LoaderCircle className="student-save-spinner" size={16} /> Saving…</> : creating ? 'Save student' : 'Save changes'}
                {!saving && <ArrowRight size={16} />}
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
