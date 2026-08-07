import { useState } from 'react';
import Button from '../ui/Button.jsx';
import Select from '../ui/Select.jsx';

export default function EmployeeAccountLinkForm({
  employee,
  users,
  loading = false,
  onSubmit,
}) {
  const [userId, setUserId] = useState('');
  const available = users.filter((user) => (
    !user.employee_profile
    || String(user.employee_profile.id) === String(employee.id)
  ));

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(userId);
      }}
    >
      <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-950">
        Link an existing active account to <strong>{employee.full_name}</strong>. This avoids creating a duplicate identity.
      </div>
      <Select
        label="Existing user account"
        aria-label="Existing user account"
        value={userId}
        onChange={(event) => setUserId(event.target.value)}
        required
      >
        <option value="">Select account</option>
        {available.map((user) => (
          <option key={user.id} value={user.id}>
            {user.full_name} · {user.email}
          </option>
        ))}
      </Select>
      <div className="flex justify-end">
        <Button type="submit" disabled={loading || !userId}>
          {loading ? 'Linking…' : 'Link account'}
        </Button>
      </div>
    </form>
  );
}
