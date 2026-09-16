export type Role = "PLATFORM_ADMIN" | "HOSPITAL_ADMIN" | "CAMPAIGN_MANAGER" | "CLINICAL_REVIEWER";
export type CampaignStatus = "DRAFT" | "READY" | "SCHEDULED" | "RUNNING" | "PAUSED" | "COMPLETED" | "CANCELLED" | "FAILED";

export interface EligibilityCriteria {
  risk_levels: string[];
  care_settings: string[];
  discharge_after: string | null;
  discharge_before: string | null;
  condition_codes: string[];
  discharge_status: "PENDING" | null;
  communication_eligible: true | null;
  required_communication_preferences: Record<string, boolean>;
}

export interface Campaign {
  id: string;
  name: string;
  description: string | null;
  status: CampaignStatus;
  start_at: string | null;
  end_at: string | null;
  clinical_follow_up_hours: number | null;
  calling_window_start: string | null;
  calling_window_end: string | null;
  campaign_priority: number | null;
  max_retries: number | null;
  outbound_capacity: number | null;
  eligibility_criteria: EligibilityCriteria;
  created_at: string;
  updated_at: string;
}

export interface Estimate {
  total_evaluated: number;
  eligible_patients: number;
  ineligible_patients: number;
  estimated_outreach_attempts: number;
  by_risk_level: Record<string, number>;
  by_ineligibility_reason: Record<string, number>;
}

export interface EligibilityResult {
  patient_id: string;
  discharge_id: string;
  eligible: boolean;
  reasons: string[];
  follow_up_deadline: string;
  risk_level: string;
  care_setting: string;
}

export interface EligibilityPage {
  total: number;
  limit: number;
  offset: number;
  items: EligibilityResult[];
}

export const mutationRoles: Role[] = ["HOSPITAL_ADMIN", "CAMPAIGN_MANAGER"];
export const canManageCampaigns = (role: Role | undefined) => Boolean(role && mutationRoles.includes(role));

export const formatDate = (value: string | null) => value ? new Date(value).toLocaleString() : "—";
export const asIso = (value: string) => value ? new Date(value).toISOString() : null;
