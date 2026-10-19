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

export type ProjectStatus = 'Draft' | 'Formatting' | 'Needs review' | 'Ready to submit';

export interface Project {
  id: string;
  title: string;
  abstract: string;
  keywords: string[];
  field: string;
  targetJournalId?: string;
  targetJournalTitle?: string;
  status: ProjectStatus;
  updatedAt: string;
  wordCount: number;
  fileName?: string;
  fileSize?: string;
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
  abstract?: string;
  keywords?: string[];
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
