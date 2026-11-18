import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Award,
  CheckCircle2,
  Clock3,
  FileSearch,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  UserRound,
  X,
  XCircle,
} from "lucide-react";
import api from "../../services/api";
import "./RecruiterAssessmentResults.css";

const REVIEW_API = "/recruiter/assessments/reviews";

export default function RecruiterAssessmentResults() {
  const [results, setResults] = useState([]);
  const [selectedResult, setSelectedResult] = useState(null);

  const [violations, setViolations] = useState([]);
  const [violationSummary, setViolationSummary] = useState(null);

  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [violationLoading, setViolationLoading] = useState(false);
  const [reviewSubmitting, setReviewSubmitting] = useState(false);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [reviewNotes, setReviewNotes] = useState("");

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    fetchResults();
  }, []);

  const fetchResults = async () => {
    try {
      setLoading(true);
      setError("");
      setSuccess("");

      const response = await api.get(REVIEW_API, {
        params: {
          review_status: statusFilter,
        },
      });

      setResults(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Unable to load assessment review results."
      );
    } finally {
      setLoading(false);
    }
  };

  const fetchViolations = async (assignmentId) => {
    if (!assignmentId) {
      setViolations([]);
      setViolationSummary(null);
      return;
    }

    try {
      setViolationLoading(true);

      const response = await api.get(
        `/recruiter/proctoring/assignments/${assignmentId}/violations`
      );

      setViolations(response.data.violations || []);
      setViolationSummary(response.data);
    } catch (err) {
      setViolations([]);
      setViolationSummary(null);

      console.error(
        "Unable to load proctoring history:",
        err.response?.data || err.message
      );
    } finally {
      setViolationLoading(false);
    }
  };

  const openResult = async (result) => {
    try {
      setDetailLoading(true);
      setSelectedResult(null);
      setViolations([]);
      setViolationSummary(null);
      setReviewNotes(result.review_notes || "");
      setError("");
      setSuccess("");

      const response = await api.get(
        `/recruiter/assessments/results/${result.id}`
      );

      const detail = {
        ...result,
        ...response.data,
        review_status: result.review_status,
        review_notes: result.review_notes,
        reviewed_at: result.reviewed_at,
        automatic_score_qualified: result.automatic_score_qualified,
      };

      setSelectedResult(detail);

      await fetchViolations(
        detail.assignment_id || result.assignment_id
      );
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Unable to load candidate details."
      );
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setSelectedResult(null);
    setViolations([]);
    setViolationSummary(null);
    setReviewNotes("");
  };

  const submitReview = async (decision) => {
    if (!selectedResult) return;

    const decisionLabel =
      decision === "QUALIFIED" ? "Qualified" : "Not Qualified";

    const confirmed = window.confirm(
      `Confirm final decision: ${decisionLabel}? This decision cannot be changed.`
    );

    if (!confirmed) return;

    try {
      setReviewSubmitting(true);
      setError("");
      setSuccess("");

      await api.post(
        `${REVIEW_API}/${selectedResult.id}/review`,
        {
          decision,
          review_notes: reviewNotes.trim() || null,
        }
      );

      setSuccess(
        `Final decision saved: ${decisionLabel}. Candidate has been notified.`
      );

      closeDetail();
      await fetchResults();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Unable to submit recruiter review."
      );
    } finally {
      setReviewSubmitting(false);
    }
  };

  const filteredResults = results.filter((item) => {
    const term = search.trim().toLowerCase();

    if (!term) return true;

    return (
      (item.candidate_name || "").toLowerCase().includes(term) ||
      (item.candidate_email || "").toLowerCase().includes(term) ||
      (item.job_title || "").toLowerCase().includes(term)
    );
  });

  const pendingCount = results.filter(
    (item) => item.review_status === "PENDING_REVIEW"
  ).length;

  const qualifiedCount = results.filter(
    (item) => item.review_status === "QUALIFIED"
  ).length;

  const notQualifiedCount = results.filter(
    (item) => item.review_status === "NOT_QUALIFIED"
  ).length;

  const flaggedCount = results.filter(
    (item) => item.is_flagged_for_review
  ).length;

  const formatDate = (value) =>
    value ? new Date(value).toLocaleString() : "Not available";

  const formatTime = (seconds) => {
    if (!seconds) return "0 min";
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  };

  const getViolationLabel = (type) => {
    const labels = {
      AI_PHONE_DETECTED: "Mobile phone detected",
      AI_MULTIPLE_PEOPLE_DETECTED: "Multiple people detected",
      TAB_SWITCH: "Tab switched",
      WINDOW_BLUR: "Window lost focus",
      FULLSCREEN_EXIT: "Fullscreen exited",
      CAMERA_DISCONNECTED: "Camera disconnected",
      RECORDING_STOPPED: "Recording stopped",
    };

    return labels[type] || type?.replaceAll("_", " ");
  };

  const isDangerViolation = (type) =>
    type?.includes("PHONE") || type?.includes("MULTIPLE");

  const getReviewStatusLabel = (status) => {
    if (status === "QUALIFIED") return "Qualified";
    if (status === "NOT_QUALIFIED") return "Not Qualified";
    return "Pending Review";
  };

  const getReviewStatusClass = (status) => {
    if (status === "QUALIFIED") return "qualified";
    if (status === "NOT_QUALIFIED") return "not-qualified";
    return "pending";
  };

  return (
    <main className="assessment-page">
      <div className="assessment-container">
        <header className="assessment-heading">
          <div>
            <div className="assessment-eyebrow">
              RECRUITMENT WORKSPACE
            </div>
            <h1>Assessment Results</h1>
            <p>
              Review candidate scorecards and make final assessment
              decisions.
            </p>
          </div>

          <button
            className="ar-button ar-button-primary"
            onClick={fetchResults}
            disabled={loading}
          >
            <RefreshCw
              size={17}
              className={loading ? "ar-spin" : ""}
            />
            Refresh Results
          </button>
        </header>

        {error && (
          <div className="ar-error">
            <AlertTriangle size={19} />
            <span>{error}</span>
            <button
              onClick={() => setError("")}
              aria-label="Dismiss error"
            >
              <X size={17} />
            </button>
          </div>
        )}

        {success && (
          <div className="ar-notice ar-notice-success">
            <CheckCircle2 size={19} />
            <span>{success}</span>
          </div>
        )}

        <section className="ar-stats">
          <SummaryCard
            icon={<Activity />}
            title="Total Assessments"
            value={results.length}
            tone="dark"
          />

          <SummaryCard
            icon={<Clock3 />}
            title="Pending Review"
            value={pendingCount}
            tone="orange"
          />

          <SummaryCard
            icon={<CheckCircle2 />}
            title="Qualified"
            value={qualifiedCount}
            tone="green"
          />

          <SummaryCard
            icon={<XCircle />}
            title="Not Qualified"
            value={notQualifiedCount}
            tone="red"
          />
        </section>

        <section className="ar-filter-panel">
          <div className="ar-section-title">
            <div>
              <h2>Candidate Scorecards</h2>
              <p>
                Review performance and submit your final decision.
              </p>
            </div>

            <span className="ar-count">
              {filteredResults.length} results
            </span>
          </div>

          <div className="ar-filters">
            <div className="ar-search">
              <Search size={18} />

              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search candidate, email or job..."
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setSelectedResult(null);
              }}
              aria-label="Filter by review status"
            >
              <option value="ALL">All Reviews</option>
              <option value="PENDING_REVIEW">Pending Review</option>
              <option value="QUALIFIED">Qualified</option>
              <option value="NOT_QUALIFIED">Not Qualified</option>
            </select>
          </div>
        </section>

        <section className="ar-table-card">
          {loading ? (
            <div className="ar-empty">
              <RefreshCw className="ar-spin" size={25} />
              <h3>Loading assessment results</h3>
              <p>Please wait while we fetch the latest results.</p>
            </div>
          ) : filteredResults.length === 0 ? (
            <div className="ar-empty">
              <FileSearch size={38} />
              <h3>No assessment results found</h3>
              <p>
                Completed assessments will appear here for recruiter
                review.
              </p>
            </div>
          ) : (
            <div className="ar-table-scroll">
              <table className="ar-table">
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Job</th>
                    <th>Score</th>
                    <th>Percentage</th>
                    <th>Review Status</th>
                    <th>Action</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredResults.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <div className="ar-candidate">
                          <div className="ar-avatar">
                            {(item.candidate_name || "C")
                              .charAt(0)
                              .toUpperCase()}
                          </div>

                          <div>
                            <strong>
                              {item.candidate_name || "Candidate"}
                            </strong>
                            <small>{item.candidate_email}</small>
                          </div>
                        </div>
                      </td>

                      <td>{item.job_title || "—"}</td>

                      <td>
                        <strong>
                          {item.obtained_marks} / {item.total_marks}
                        </strong>
                      </td>

                      <td>
                        <strong>
                          {Number(item.percentage || 0).toFixed(1)}%
                        </strong>
                      </td>

                      <td>
                        <span
                          className={`ar-status ${getReviewStatusClass(
                            item.review_status
                          )}`}
                        >
                          {getReviewStatusLabel(item.review_status)}
                        </span>
                      </td>

                      <td>
                        <button
                          className="ar-link-button"
                          onClick={() => openResult(item)}
                        >
                          Review Scorecard <span>→</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {(selectedResult || detailLoading) && (
          <section className="ar-detail-panel">
            <div className="ar-detail-heading">
              <div>
                <span className="assessment-eyebrow">
                  CANDIDATE REVIEW
                </span>
                <h2>Assessment Details</h2>
              </div>

              <button
                className="ar-close-button"
                onClick={closeDetail}
                aria-label="Close details"
              >
                <X size={20} />
              </button>
            </div>

            {detailLoading ? (
              <div className="ar-empty">
                <RefreshCw className="ar-spin" size={24} />
                <p>Loading candidate details...</p>
              </div>
            ) : (
              <>
                <div className="ar-detail-grid">
                  <DetailCard
                    icon={<UserRound />}
                    title="Candidate"
                    value={selectedResult.candidate_name}
                  />

                  <DetailCard
                    icon={<Award />}
                    title="Assessment Score"
                    value={`${selectedResult.obtained_marks ?? 0} / ${
                      selectedResult.total_marks ?? 0
                    }`}
                  />

                  <DetailCard
                    icon={<Activity />}
                    title="Percentage"
                    value={`${Number(
                      selectedResult.percentage || 0
                    ).toFixed(1)}%`}
                  />

                  <DetailCard
                    title="Correct Answers"
                    value={selectedResult.correct_count}
                  />

                  <DetailCard
                    title="Incorrect Answers"
                    value={selectedResult.incorrect_count}
                  />

                  <DetailCard
                    title="Unanswered"
                    value={selectedResult.unanswered_count}
                  />

                  <DetailCard
                    icon={<Clock3 />}
                    title="Time Taken"
                    value={formatTime(
                      selectedResult.time_taken_seconds
                    )}
                  />

                  <DetailCard
                    title="Passing Marks"
                    value={selectedResult.passing_marks}
                  />

                  <DetailCard
                    title="Automatic Threshold"
                    value={
                      selectedResult.automatic_score_qualified
                        ? "Threshold Met"
                        : "Threshold Not Met"
                    }
                  />
                </div>

                <div className="ar-notice">
                  <strong>Recruiter decision:</strong>{" "}
                  {getReviewStatusLabel(
                    selectedResult.review_status
                  )}
                </div>

                {selectedResult.review_status === "PENDING_REVIEW" && (
                  <div className="ar-review-action-panel">
                    <h3>Submit Final Decision</h3>

                    <p>
                      Review the scorecard and proctoring history before
                      making your final decision. This decision cannot be
                      changed after submission.
                    </p>

                    <label
                      htmlFor="assessment-review-notes"
                      style={{
                        display: "block",
                        marginBottom: "8px",
                        fontWeight: 600,
                      }}
                    >
                      Review Notes (Optional)
                    </label>

                    <textarea
                      id="assessment-review-notes"
                      value={reviewNotes}
                      onChange={(e) => setReviewNotes(e.target.value)}
                      placeholder="Add your review notes..."
                      rows={4}
                      maxLength={2000}
                      style={{
                        width: "100%",
                        resize: "vertical",
                        padding: "12px",
                        borderRadius: "10px",
                        border: "1px solid #d5d9e2",
                        fontFamily: "inherit",
                        marginBottom: "16px",
                      }}
                    />

                    <div
                      style={{
                        display: "flex",
                        gap: "12px",
                        flexWrap: "wrap",
                      }}
                    >
                      <button
                        className="ar-button ar-button-primary"
                        disabled={reviewSubmitting}
                        onClick={() => submitReview("QUALIFIED")}
                      >
                        <CheckCircle2 size={17} />
                        Mark Qualified
                      </button>

                      <button
                        className="ar-button"
                        disabled={reviewSubmitting}
                        onClick={() => submitReview("NOT_QUALIFIED")}
                        style={{
                          background: "#fff",
                          color: "#b42318",
                          border: "1px solid #f0b7b7",
                        }}
                      >
                        <XCircle size={17} />
                        Mark Not Qualified
                      </button>
                    </div>
                  </div>
                )}

                {selectedResult.review_status !== "PENDING_REVIEW" && (
                  <div className="ar-notice">
                    <strong>Final Decision Submitted</strong>
                    <p>
                      Decision:{" "}
                      {getReviewStatusLabel(
                        selectedResult.review_status
                      )}
                    </p>

                    {selectedResult.review_notes && (
                      <p>
                        <strong>Review Notes:</strong>{" "}
                        {selectedResult.review_notes}
                      </p>
                    )}

                    {selectedResult.reviewed_at && (
                      <p>
                        <strong>Reviewed At:</strong>{" "}
                        {formatDate(selectedResult.reviewed_at)}
                      </p>
                    )}
                  </div>
                )}

                <div className="ar-breakdown">
                  <h3>Assessment Question Breakdown</h3>
                  <pre>
                    {JSON.stringify(
                      selectedResult.question_breakdown || [],
                      null,
                      2
                    )}
                  </pre>
                </div>

                <div className="ar-proctoring">
                  <div className="ar-proctoring-heading">
                    <div>
                      <span className="assessment-eyebrow">
                        AI PROCTORING
                      </span>
                      <h3>Violation History</h3>
                      <p>Review recorded assessment warnings.</p>
                    </div>

                    {violationSummary && (
                      <span
                        className={`ar-review-badge ${
                          violationSummary.is_flagged_for_review
                            ? "flagged"
                            : "clear"
                        }`}
                      >
                        {violationSummary.is_flagged_for_review
                          ? "Flagged for Review"
                          : "Not Flagged"}
                      </span>
                    )}
                  </div>

                  {violationLoading ? (
                    <div className="ar-empty">
                      <RefreshCw className="ar-spin" size={22} />
                      <p>Loading proctoring history...</p>
                    </div>
                  ) : !violationSummary ? (
                    <div className="ar-notice">
                      Proctoring history is unavailable. Confirm that
                      the assessment assignment ID is included in the
                      results API.
                    </div>
                  ) : (
                    <>
                      <div className="ar-detail-grid ar-violation-stats">
                        <DetailCard
                          title="Total Warnings"
                          value={violationSummary.warning_count || 0}
                        />

                        <DetailCard
                          title="Recorded Violations"
                          value={violations.length}
                        />
                      </div>

                      {violations.length === 0 ? (
                        <div className="ar-notice ar-notice-success">
                          <ShieldCheck size={20} />
                          No violations recorded for this assessment.
                        </div>
                      ) : (
                        <div className="ar-violation-list">
                          {violations.map((item) => (
                            <article
                              className="ar-violation"
                              key={item.id}
                            >
                              <div className="ar-violation-icon">
                                <AlertTriangle
                                  size={19}
                                  className={
                                    isDangerViolation(
                                      item.violation_type
                                    )
                                      ? "danger-icon"
                                      : ""
                                  }
                                />
                              </div>

                              <div className="ar-violation-content">
                                <strong>
                                  {getViolationLabel(
                                    item.violation_type
                                  )}
                                </strong>
                                <small>
                                  {formatDate(item.detected_at)}
                                </small>
                              </div>

                              <div className="ar-violation-meta">
                                {item.confidence !== null &&
                                  item.confidence !== undefined && (
                                    <span>
                                      Confidence:{" "}
                                      {(
                                        item.confidence * 100
                                      ).toFixed(1)}
                                      %
                                    </span>
                                  )}

                                <span
                                  className={`ar-violation-tag ${
                                    isDangerViolation(
                                      item.violation_type
                                    )
                                      ? "danger"
                                      : "warning"
                                  }`}
                                >
                                  {item.violation_type?.startsWith(
                                    "AI_"
                                  )
                                    ? "AI Detection"
                                    : "Browser Warning"}
                                </span>
                              </div>
                            </article>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </>
            )}
          </section>
        )}
      </div>
    </main>
  );
}

function SummaryCard({ icon, title, value, tone }) {
  return (
    <article className={`ar-stat-card ${tone}`}>
      <div className="ar-stat-icon">{icon}</div>

      <div>
        <p>{title}</p>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

function DetailCard({ icon, title, value }) {
  return (
    <article className="ar-detail-card">
      <div className="ar-detail-label">
        {icon}
        <span>{title}</span>
      </div>

      <strong>{value ?? "N/A"}</strong>
    </article>
  );
}