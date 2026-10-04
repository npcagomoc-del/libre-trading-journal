import { render, screen, fireEvent, within } from '@testing-library/react';
import DateRangePicker from './DateRangePicker';

test('date panel escapes clipped dashboard and stays within viewport', () => {
  const { container } = render(<div style={{ overflow: 'hidden', isolation: 'isolate' }}><DateRangePicker dateFrom="" dateTo="" onChange={() => {}} /></div>);
  fireEvent.click(screen.getByRole('button', { name: 'All time' }));
  const panel = screen.getByRole('dialog', { name: 'Choose a date range' });
  expect(container.contains(panel)).toBe(false);
  expect(panel).toHaveStyle({ position: 'fixed', overflowY: 'auto' });
  expect(parseFloat(panel.style.left)).toBeGreaterThanOrEqual(12);
  expect(parseFloat(panel.style.width)).toBeLessThanOrEqual(window.innerWidth - 24);
  fireEvent.resize(window);
  expect(screen.getByRole('dialog')).toBeInTheDocument();
});

test('portal presets still apply dates and close the panel', () => {
  const change = jest.fn();
  render(<DateRangePicker dateFrom="" dateTo="" onChange={change} />);
  fireEvent.click(screen.getByRole('button', { name: 'All time' }));
  const today = within(screen.getByRole('dialog')).getByRole('button', { name: 'Today', exact: true });
  fireEvent.mouseDown(today);
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  fireEvent.click(today);
  expect(change).toHaveBeenCalledWith(expect.objectContaining({ dateFrom: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/) }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('outside click and Escape dismiss the date picker', () => {
  render(<DateRangePicker dateFrom="" dateTo="" onChange={() => {}} />);
  const trigger = screen.getByRole('button', { name: 'All time' });
  fireEvent.click(trigger);
  fireEvent.mouseDown(document.body);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  fireEvent.click(trigger);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
