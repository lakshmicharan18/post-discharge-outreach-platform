export type SimulationRun = {
  id: string;
  scenario_name: string;
  simulated_now: string;
  configured_capacity: number;
};

export type SimulationSummary = {
  run_id: string; simulated_start_time: string; simulated_now: string; total_tasks: number;
  completed: number; pending: number; active: number; retry_scheduled: number;
  callback_scheduled: number; manual_follow_up: number; failed: number; total_attempts: number;
  simulation_event_count: number; status: string; total_simulation_steps: number;
  simulated_duration_minutes: number; max_observed_active_calls: number;
  capacity_exceeded: boolean; outcome_counts: Record<string, number>;
};

export type SimulationTask = {
  scenario_key: string; risk: string; state: string; attempt_count: number;
  priority_score: number; next_eligible_at: string; clinical_deadline: string;
  last_outcome: string | null;
};

export type SimulationEvent = {
  sequence_number: number; event_type: string; simulated_at: string;
  safe_payload: Record<string, unknown>;
};
