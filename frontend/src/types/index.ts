export interface User {
  id: string;
  fullName: string;
  email: string;
  avatarInitials?: string;
  plan?: string;
  role?: string;
}

export const DEFAULT_USER_PLAN = 'Pro plan';

export function getAvatarInitials(fullName: string): string {
  if (!fullName) return 'U';
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'U';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export type ProjectStatus = 'Draft' | 'Formatting' | 'Needs review' | 'Ready to submit' | 'Submitted' | string;

export interface ManuscriptMetadata {
  fileName: string;
  sizeBytes: number;
  uploadedAt: string;
  available: boolean;
  expiresAt: string;
}

export interface TargetJournalMetadata {
  id: string;
  title: string;
  publisher: string;
}

export interface ProjectActivityEvent {
  id: string;
  projectId?: string | null;
  projectTitle?: string | null;
  eventType: string;
  details: Record<string, any>;
  journalTitle?: string | null;
  createdAt: string;
}

export interface Project {
  id: string;
  title: string;
  abstract?: string | null;
  keywords: string[];
  field: string;
  researchField?: string | null;
  targetJournalId?: string;
  targetJournalTitle?: string;
  targetJournal?: TargetJournalMetadata | null;
  guidelineRuleSet?: { id: string; name: string; version: number; source: string } | null;
  status: ProjectStatus;
  createdAt?: string;
  updatedAt: string;
  wordCount?: number;
  fileName?: string;
  fileSize?: string;
  shortlistedCount?: number;
  hasManuscript?: boolean;
  manuscript?: ManuscriptMetadata | null;
  counts?: { conversions: number; complianceReports: number };
  recentActivity?: ProjectActivityEvent[];
}

export interface Journal {
  id: string;
  title: string;
  publisher: string;
  issn: string;
  subjectCategory: string;
  citeScore?: number | null;
  impactFactor?: number | null;
  quartile?: 'Q1' | 'Q2' | 'Q3' | 'Q4' | string | null;
  aimsAndScope: string;
  openAccessType?: 'Open access' | 'Hybrid' | 'Subscription' | string | null;
  reviewWeeks?: number | null;
  acceptanceRate?: number | null; // percentage e.g. 22
  isShortlisted?: boolean;
  matchScore?: number; // e.g. 96
  matchTag?: string | null; // e.g. "Best fit"
  rawSimilarity?: number | null;
}

export interface MatchRequest {
  title?: string;
  abstract?: string;
  keywords?: string[];
  limit?: number;
  projectId?: string;
}

export interface MatchMeta {
  model: string;
  tookMs: number;
  totalJournals: number;
}

export interface MatchResponse {
  results: Journal[];
  meta: MatchMeta;
}

export interface CreateProjectPayload {
  title: string;
  researchField?: string;
  field?: string;
  abstract?: string;
  keywords?: string[];
}

export interface PatchProjectPayload {
  title?: string;
  researchField?: string;
  field?: string;
  abstract?: string | null;
  keywords?: string[];
  status?: string;
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
  page: number;
  pageSize: number;
}

export interface GuidelineExtractionWarning {
  code: string;
  message: string;
  path?: string | null;
}

export interface GuidelineExtractionError {
  code: string;
  message: string;
}

export interface GuidelineFieldProvenance {
  confidence: 'high' | 'medium' | 'low';
  evidence?: string | null;
  articleType?: string | null;
  edited?: boolean;
}

export interface GuidelineExtractionDraft {
  schemaVersion: number;
  rules: Record<string, any>;
  fields?: Record<string, GuidelineFieldProvenance>;
  alternatives?: Record<string, Array<{ value: any; evidence?: string | null; articleType?: string | null }>>;
}

export interface GuidelineExtractionJob {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  step: 'queued' | 'fetching' | 'cleaning' | 'extracting' | 'validating' | 'done';
  cached: boolean;
  sourceType: 'url' | 'text';
  sourceUrl?: string | null;
  finalUrl?: string | null;
  journalId?: string | null;
  projectId?: string | null;
  source?: {
    title?: string | null;
    wordCount: number;
    language: string;
    truncated: boolean;
  } | null;
  warnings: GuidelineExtractionWarning[];
  draft?: GuidelineExtractionDraft | null;
  error?: GuidelineExtractionError | null;
  createdAt: string;
  completedAt?: string | null;
}

export interface GuidelineRuleSet {
  id: string;
  name: string;
  journalId?: string | null;
  journalTitle?: string | null;
  origin: 'extracted' | 'manual' | 'seed';
  version: number;
  isActive: boolean;
  isSystem: boolean;
  schemaVersion: number;
  rules: Record<string, any>;
  provenance?: Record<string, any>;
  sourceUrl?: string | null;
  lineageId: string;
  createdAt: string;
  updatedAt?: string | null;
}

export interface CreateExtractionPayload {
  sourceType: 'url' | 'text';
  url?: string;
  text?: string;
  journalId?: string | null;
  projectId?: string | null;
}

export interface ConfirmExtractionPayload {
  rules: Record<string, any>;
  name?: string | null;
  journalId?: string | null;
  projectId?: string | null;
  acknowledgedFields?: string[];
}

export interface CreateRuleSetPayload {
  name: string;
  rules: Record<string, any>;
  journalId?: string | null;
  sourceUrl?: string | null;
}

export interface PatchRuleSetPayload {
  name?: string | null;
  rules?: Record<string, any> | null;
}

export interface EffectiveRulesResponse {
  ruleSet: GuidelineRuleSet | null;
  source: 'project' | 'user' | 'system' | null;
}

export interface GuidelineRule {
  id: string;
  journalId?: string;
  sourceUrl?: string;
  maxWordCount: number;
  maxAbstractWords: number;
  citationStyle: 'Vancouver' | 'APA 7' | 'IEEE' | 'Harvard' | 'Chicago';
  requiredSections: string[];
  columnLayout: 'Single column' | 'Double column';
  lineSpacing?: 'Single' | '1.5 lines' | 'Double';
  margins?: { top: number; bottom: number; left: number; right: number };
  fontFamily?: string;
  fontSizes?: { title: number; text: number; figCaption: number; tblCaption: number };
}

export interface ConversionJob {
  id: string;
  fileName: string;
  fileSize: string;
  sourceFormat: 'DOCX' | 'TEX';
  targetFormat: 'TEX' | 'DOCX';
  date: string;
  status: 'Completed' | 'Processing' | 'Failed';
  details?: string;
  downloadUrl?: string;
}

export interface TransformationJob {
  id: string;
  manuscriptName: string;
  fileSize: string;
  targetJournal: string;
  date: string;
  status: 'Completed' | 'Processing' | 'Failed';
  changesApplied: {
    singleToDoubleColumn: boolean;
    citationStyle: string;
    marginsUpdated: boolean;
    manualReviewItemsCount: number;
  };
}

export interface ComplianceCheckItem {
  id: string;
  name: string;
  description: string;
  status: 'passed' | 'failed';
  currentValue?: string;
  requirementValue?: string;
  suggestedFix?: string;
}

export interface ComplianceReport {
  id: string;
  projectId: string;
  projectTitle: string;
  journalId: string;
  journalTitle: string;
  status: 'Passed' | 'Failed';
  checksPassed: number;
  checksFailed: number;
  generatedDate: string;
  checks: ComplianceCheckItem[];
  nextSteps: {
    badge: string;
    title: string;
    description: string;
    actionText: string;
  }[];
}

export interface ActivityItem {
  id: string;
  title: string;
  subtitle: string;
  timestamp: string;
  type: 'compliance' | 'journal' | 'conversion' | 'project';
}
