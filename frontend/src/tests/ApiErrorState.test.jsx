import { render, screen } from '@testing-library/react';
import Alert from '../components/ui/Alert.jsx';

test('renders API error state', () => {
  render(<Alert type="error">Failed to load</Alert>);
  expect(screen.getByText('Failed to load')).toBeInTheDocument();
});
