
import React from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate
} from 'react-router-dom';

import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

// Public Pages
import Home from './pages/Home';
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';
import ForgotPassword from './pages/auth/ForgotPassword';
import ResetPassword from './pages/auth/ResetPassword';
import VerifyEmail from './pages/auth/VerifyEmail';

// Candidate Pages
import CandidateDashboard from './pages/candidate/CandidateDashboard';
import CandidateProfile from './pages/candidate/CandidateProfile';
import ExploreJobs from './pages/candidate/ExploreJobs';
import SavedJobs from './pages/candidate/SavedJobs';
import MyApplications from './pages/candidate/MyApplications';
import ResumeManagement from './pages/candidate/ResumeManagement';
import ResumeBuilder from './pages/candidate/ResumeBuilder';
import FirstRoundAssessments from './pages/candidate/FirstRoundAssessments';
import TakeAssessment from './pages/candidate/TakeAssessment';
import AssessmentResultView from './pages/candidate/AssessmentResultView';
import SkillGapAnalysis from './pages/candidate/SkillGapAnalysis';
import MockInterviewPractice from './pages/candidate/MockInterviewPractice';
import TechnicalQuiz from './pages/candidate/TechnicalQuiz';

// Recruiter Pages
import RecruiterDashboard from './pages/recruiter/RecruiterDashboard';
import RecruiterJobs from './pages/recruiter/RecruiterJobs';
import QuestionBank from './pages/recruiter/QuestionBank';
import ApplicantPipeline from './pages/recruiter/ApplicantPipeline';
import RecruiterAssessmentResults from './pages/recruiter/RecruiterAssessmentResults';
import CandidateComparison from './pages/recruiter/CandidateComparison';
import InterviewScheduler from './pages/recruiter/InterviewScheduler';
import CompanyProfile from './pages/recruiter/CompanyProfile';

// Admin Pages
import AdminDashboard from './pages/admin/AdminDashboard';

// ROOT REDIRECT
function RootRedirect() {
  const { user, token, loading } = useAuth();

  if (loading) {
    return null;
  }

  // Public homepage for logged-out users
  if (!token || !user) {
    return <Home />;
  }

  const role = user.role?.toUpperCase();

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
        <Routes>

          {/* PUBLIC HOMEPAGE */}
          <Route path="/" element={<RootRedirect />} />
          <Route path="/home" element={<Home />} />

          {/* AUTHENTICATION ROUTES */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email" element={<VerifyEmail />} />

          {/* CANDIDATE ROUTES */}
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

          </Route>

          {/* RECRUITER ROUTES */}
          <Route element={<ProtectedRoute allowedRoles={['RECRUITER']} />}>

            <Route
              path="/recruiter/dashboard"
              element={<RecruiterDashboard />}
            />

            <Route
              path="/recruiter/company"
              element={<CompanyProfile />}
            />

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

          </Route>

          {/* ADMIN ROUTES */}
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
              path="/admin/question-bank"
              element={<QuestionBank />}
            />

            <Route
              path="/admin/audit-logs"
              element={<AdminDashboard />}
            />

          </Route>

          {/* FALLBACK */}
          <Route path="*" element={<Navigate to="/" replace />} />

        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
