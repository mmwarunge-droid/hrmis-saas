import { useMemo, useState } from 'react';
import { ShieldCheck, UserCog } from 'lucide-react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

const TENANT_ROLES = [
  'CLIENT_ADMIN',
  'ORGANIZATION_OWNER',
  'HR_CONSULTANT',
  'MANAGER',
  'EMPLOYEE',
];
const ORGANIZATION_ADMIN_ROLES = ['MANAGER', 'EMPLOYEE'];

export default function UserAccountEditForm({
  account,
  currentUserId,
  isSuperAdmin,
  loading = false,
  onSubmit,
}) {
  const [firstName, setFirstName] = useState(
    () => account?.first_name || '',
  );
  const [lastName, setLastName] = useState(
    () => account?.last_name || '',
  );
  const [status, setStatus] = useState(
    () => (account?.is_active ? 'active' : 'inactive'),
  );
  const [roles, setRoles] = useState(
    () => account?.roles || [],
  );

  const availableRoles = useMemo(() => {
    if (!isSuperAdmin) return ORGANIZATION_ADMIN_ROLES;
    if (!account?.tenant_id) return ['SUPER_ADMIN'];
    return TENANT_ROLES;
  }, [account?.tenant_id, isSuperAdmin]);

  const toggleRole = (role) => {
    setRoles((current) => (
      current.includes(role)
        ? current.filter((item) => item !== role)
        : [...current, role]
    ));
  };

  const isCurrentUser = String(account?.id) === String(currentUserId);

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      profile: {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        is_active: status === 'active',
      },
      roles,
    });
  };

  return (
    <form className="space-y-6" onSubmit={submit}>
      <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-950">
        <div className="flex items-start gap-3">
          <UserCog className="mt-0.5 shrink-0" size={18} />
          <div>
            <p className="font-semibold">{account?.full_name}</p>
            <p className="mt-1 text-blue-800">{account?.email}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="First name"
          value={firstName}
          onChange={(event) => setFirstName(event.target.value)}
          required
        />
        <Input
          label="Last name"
          value={lastName}
          onChange={(event) => setLastName(event.target.value)}
          required
        />
        <Select
          label="Account status"
          aria-label="Account status"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          disabled={isCurrentUser}
          hint={isCurrentUser ? 'You cannot deactivate your own account.' : 'Deactivation revokes active sessions immediately.'}
        >
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </Select>
      </div>

      <section className="border-t border-slate-100 pt-5">
        <div className="mb-4 flex items-start gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-violet-50 text-violet-700">
            <ShieldCheck size={18} />
          </span>
          <div>
            <h3 className="font-bold text-slate-950">Access roles</h3>
            <p className="text-xs leading-5 text-slate-500">
              Keep access limited to the responsibilities this person performs.
            </p>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {availableRoles.map((role) => (
            <label
              key={role}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 text-sm hover:border-blue-200 hover:bg-blue-50/40"
            >
              <input
                type="checkbox"
                checked={roles.includes(role)}
                onChange={() => toggleRole(role)}
                disabled={isCurrentUser && role === 'SUPER_ADMIN'}
                className="h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-400"
              />
              <span className="font-semibold text-slate-800">
                {role.replaceAll('_', ' ')}
              </span>
            </label>
          ))}
        </div>
        {roles.length === 0 && (
          <p className="mt-3 text-xs font-medium text-red-600">
            Select at least one role.
          </p>
        )}
      </section>

      <div className="flex justify-end gap-3 border-t border-slate-100 pt-5">
        <Button type="submit" disabled={loading || roles.length === 0}>
          {loading ? 'Saving...' : 'Save account'}
        </Button>
      </div>
    </form>
  );
}
