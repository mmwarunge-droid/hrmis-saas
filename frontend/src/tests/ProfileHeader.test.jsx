import { render, screen, within } from '@testing-library/react';
import ProfileHeader from '../components/employees/ProfileHeader.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Tabs from '../components/ui/Tabs.jsx';

test('keeps identity, authorized actions and tabs outside the decorative cover', () => {
  const name = 'Mary Example with a long family name';
  const { container } = render(
    <ProfileHeader name={name} status={<Badge>probation</Badge>}
      avatar={<Avatar name={name} size="xl" />}
      subtitle="Senior People Operations Specialist · International People Operations"
      coverStyle={{ backgroundImage: 'url(/synthetic-cover.png)' }}
      actions={<Button>Edit employee</Button>}
      tabs={<Tabs items={[{ value: 'personal', label: 'Personal' }]} value="personal" onChange={() => {}} />} />,
  );
  const cover = container.querySelector('[data-profile-cover]');
  const identity = container.querySelector('[data-profile-identity]');
  const body = container.querySelector('[data-profile-body]');
  const tabs = container.querySelector('[data-profile-tabs]');
  expect(within(identity).getByRole('heading', { name })).toBeVisible();
  expect(within(identity).getByText('probation')).toBeVisible();
  expect(cover).toBeEmptyDOMElement();
  expect(cover).toHaveAttribute('aria-hidden', 'true');
  expect(cover.nextElementSibling).toBe(body);
  expect(body.nextElementSibling).toBe(tabs);
  expect(within(body).getByRole('button', { name: 'Edit employee' })).toBeVisible();
  expect(within(tabs).getByRole('tab', { name: 'Personal' })).toBeVisible();
  expect(within(body).getByText('ME')).toBeVisible();
});

test('keeps custom avatar alt text and allows profiles without actions or tabs', () => {
  const { container } = render(<ProfileHeader name="Li" avatar={<Avatar name="Li" src="/synthetic-avatar.png" size="xl" />} subtitle="Role not assigned" />);
  expect(screen.getByRole('img', { name: 'Li' })).toHaveAttribute('src', '/synthetic-avatar.png');
  expect(container.querySelector('[data-profile-actions]')).toBeNull();
  expect(container.querySelector('[data-profile-tabs]')).toBeNull();
});
