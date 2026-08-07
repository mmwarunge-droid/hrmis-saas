import { useState } from 'react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

export default function GoalCheckInForm({ goal, onSubmit, loading = false }) {
  const [currentValue, setCurrentValue] = useState(() => String(goal.current_value ?? 0));
  const [health, setHealth] = useState(goal.health === 'completed' ? 'on_track' : goal.health);
  const [note, setNote] = useState('');

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      current_value: Number(currentValue),
      health,
      note: note || null,
    });
  };

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-blue-700">Current goal</p>
        <p className="mt-1 font-bold text-slate-950">{goal.title}</p>
        <p className="mt-1 text-sm text-slate-600">
          {goal.current_value} of {goal.target_value} {goal.unit} · {Math.round(goal.progress_percent)}%
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label={`Current value (${goal.unit})`}
          type="number"
          min="0"
          step="0.01"
          value={currentValue}
          onChange={(event) => setCurrentValue(event.target.value)}
          required
        />
        <Select
          label="Health"
          value={health}
          onChange={(event) => setHealth(event.target.value)}
          required
        >
          <option value="on_track">On track</option>
          <option value="at_risk">At risk</option>
          <option value="off_track">Off track</option>
        </Select>
      </div>
      <label className="block space-y-1.5">
        <span className="text-[13px] font-semibold text-slate-700">Progress note</span>
        <textarea
          className="min-h-28 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition hover:border-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="What changed, what is blocked, and what happens next?"
        />
      </label>
      <div className="flex justify-end">
        <Button type="submit" disabled={loading}>
          {loading ? 'Saving…' : 'Save check-in'}
        </Button>
      </div>
    </form>
  );
}
