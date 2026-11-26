import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import SkillSphereAssistant from './components/SkillSphereAssistant';

// Public Landing & Auth Pages
const Home = lazy(() => import('./pages/Home'));
const Login = lazy(() => import('./pages/auth/Login'));
const Register = lazy(() => import('./pages/auth/Register'));
const ForgotPassword = lazy(() => import('./pages/auth/ForgotPassword'));
const ResetPassword = lazy(() => import('./pages/auth/ResetPassword'));

// Shared Support Center
const SupportTickets = lazy(() => import('./pages/SupportTickets'));

// Candidate Pages
const CandidateDashboard = lazy(() => import('./pages/candidate/CandidateDashboard'));
const CandidateProfile = lazy(() => import('./pages/candidate/CandidateProfile'));
const ExploreJobs = lazy(() => import('./pages/candidate/ExploreJobs'));
const SavedJobs = lazy(() => import('./pages/candidate/SavedJobs'));
const MyApplications = lazy(() => import('./pages/candidate/MyApplications'));
const ResumeManagement = lazy(() => import('./pages/candidate/ResumeManagement'));
const ResumeBuilder = lazy(() => import('./pages/candidate/ResumeBuilder'));
const FirstRoundAssessments = lazy(() => import('./pages/candidate/FirstRoundAssessments'));
const TakeAssessment = lazy(() => import('./pages/candidate/TakeAssessment'));
const AssessmentResultView = lazy(() => import('./pages/candidate/AssessmentResultView'));
const SkillGapAnalysis = lazy(() => import('./pages/candidate/SkillGapAnalysis'));
const MockInterviewPractice = lazy(() => import('./pages/candidate/MockInterviewPractice'));
const TechnicalQuiz = lazy(() => import('./pages/candidate/TechnicalQuiz'));

// Recruiter Pages
const RecruiterDashboard = lazy(() => import('./pages/recruiter/RecruiterDashboard'));
const RecruiterJobs = lazy(() => import('./pages/recruiter/RecruiterJobs'));
const QuestionBank = lazy(() => import('./pages/recruiter/QuestionBank'));
const ApplicantPipeline = lazy(() => import('./pages/recruiter/ApplicantPipeline'));
const RecruiterAssessmentResults = lazy(() => import('./pages/recruiter/RecruiterAssessmentResults'));
const CandidateComparison = lazy(() => import('./pages/recruiter/CandidateComparison'));
const InterviewScheduler = lazy(() => import('./pages/recruiter/InterviewScheduler'));
const CompanyProfile = lazy(() => import('./pages/recruiter/CompanyProfile'));
const RecruiterAI = lazy(() => import('./pages/recruiter/RecruiterAI'));

// Admin Pages
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'));
const PendingApprovals = lazy(() => import('./pages/admin/PendingApprovals'));
const ChatbotFeedback = lazy(() => import('./pages/admin/ChatbotFeedback'));

// Root Redirect
function RootRedirect() {
  const { user, token, loading } = useAuth();

  if (loading) return null;

  if (!token || !user) {
    return <Home />;
  }

  const role = user.role ? user.role.toUpperCase() : '';

  if (role === 'ADMIN') {
    return <Navigate to="/admin/dashboard" replace />;
  }

  if (role === 'RECRUITER') {
    return <Navigate to="/recruiter/dashboard" replace />;
  }

  return <Navigate to="/candidate/dashboard" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<div role="status" aria-live="polite" style={{ padding: '2rem', textAlign: 'center' }}>Loading page…</div>}>
        <Routes>

          {/* Public Routes */}
          <Route path="/" element={<RootRedirect />} />
          <Route path="/home" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />

          {/* Candidate Protected Routes */}
          <Route element={<ProtectedRoute allowedRoles={['CANDIDATE']} />}>
            <Route
              path="/candidate/dashboard"
              element={<CandidateDashboard />}
            />
            <Route
              path="/candidate/profile"
              element={<CandidateProfile />}
            />
            <Route
              path="/candidate/jobs"
              element={<ExploreJobs />}
            />
            <Route
              path="/candidate/saved-jobs"
              element={<SavedJobs />}
            />
            <Route
              path="/candidate/applications"
              element={<MyApplications />}
            />
            <Route
              path="/candidate/resumes"
              element={<ResumeManagement />}
            />
            <Route
              path="/candidate/resume-builder"
              element={<ResumeBuilder />}
            />
            <Route
              path="/candidate/assessments"
              element={<FirstRoundAssessments />}
            />
            <Route
              path="/candidate/first-round-assessments"
              element={<FirstRoundAssessments />}
            />
            <Route
              path="/candidate/assessments/:assignmentId/take"
              element={<TakeAssessment />}
            />
            <Route
              path="/candidate/assessments/:assignmentId/result"
              element={<AssessmentResultView />}
            />
            <Route
              path="/candidate/assessment-result/:assignmentId"
              element={<AssessmentResultView />}
            />
            <Route
              path="/candidate/matching"
              element={<SkillGapAnalysis />}
            />
            <Route
              path="/candidate/interview-practice"
              element={<MockInterviewPractice />}
            />
            <Route
              path="/candidate/technical-assessments"
              element={<TechnicalQuiz />}
            />
            <Route
              path="/candidate/support"
              element={<SupportTickets />}
            />
          </Route>

          {/* Recruiter Protected Routes */}
          <Route element={<ProtectedRoute allowedRoles={['RECRUITER']} />}>
            <Route
              path="/recruiter/dashboard"
              element={<RecruiterDashboard />}
            />
            <Route
              path="/recruiter/company"
              element={<CompanyProfile />}
            />
            <Route path="/recruiter/ai-assistant" element={<RecruiterAI />} />
            <Route
              path="/recruiter/jobs"
              element={<RecruiterJobs />}
            />
            <Route
              path="/recruiter/question-bank"
              element={<QuestionBank />}
            />
            <Route
              path="/recruiter/pipeline"
              element={<ApplicantPipeline />}
            />
            <Route
              path="/recruiter/comparison"
              element={<CandidateComparison />}
            />
            <Route
              path="/recruiter/assessments/results"
              element={<RecruiterAssessmentResults />}
            />
            <Route
              path="/recruiter/interviews"
              element={<InterviewScheduler />}
            />
            <Route
              path="/recruiter/support"
              element={<SupportTickets />}
            />
          </Route>

          {/* Admin Protected Routes */}
          <Route element={<ProtectedRoute allowedRoles={['ADMIN']} />}>
            <Route
              path="/admin/dashboard"
              element={<AdminDashboard />}
            />
            <Route
              path="/admin/users"
              element={<AdminDashboard />}
            />
            <Route
              path="/admin/recruiters"
              element={<AdminDashboard />}
            />
            <Route
              path="/admin/jobs"
              element={<AdminDashboard />}
            />
            <Route
              path="/admin/pending-approvals"
              element={<PendingApprovals />}
            />
            <Route
              path="/admin/audit-logs"
              element={<AdminDashboard />}
            />
            <Route
              path="/admin/support"
              element={<SupportTickets />}
            />
            <Route
              path="/admin/chatbot-feedback"
              element={<ChatbotFeedback />}
            />
          </Route>

          {/* Catch-all Route */}
          <Route path="*" element={<RootRedirect />} />

        </Routes>
        </Suspense>

        {/* Global SkillSphere Assistant */}
        <SkillSphereAssistant />
      </BrowserRouter>
    </AuthProvider>
  );
}
