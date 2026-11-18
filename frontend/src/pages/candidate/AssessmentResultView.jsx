import React from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  ClipboardCheck,
  ArrowRight,
  Clock3,
} from "lucide-react";

export default function AssessmentResultView() {
  const navigate = useNavigate();

  return (
    <div
      style={{
        maxWidth: "700px",
        margin: "60px auto",
        padding: "24px 16px",
      }}
    >
      <div
        className="card"
        style={{
          padding: "48px 28px",
          textAlign: "center",
        }}
      >
        <CheckCircle2
          size={68}
          color="#059669"
          style={{ margin: "0 auto 20px" }}
        />

        <h2
          style={{
            fontSize: "1.7rem",
            fontWeight: 800,
            color: "var(--text-primary)",
            marginBottom: "12px",
          }}
        >
          Assessment Submitted Successfully!
        </h2>

        <p
          style={{
            fontSize: "0.95rem",
            color: "var(--text-muted)",
            lineHeight: 1.7,
            maxWidth: "480px",
            margin: "0 auto 24px",
          }}
        >
          Your assessment responses have been submitted
          successfully. The recruiter will review your assessment
          and make the final decision. You will be notified once
          the review is complete.
        </p>

        <div
          style={{
            background: "var(--surface-subtle)",
            padding: "18px",
            borderRadius: "12px",
            marginBottom: "16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "10px",
          }}
        >
          <Clock3
            size={20}
            color="var(--primary-powder-blue-dark)"
          />

          <span
            style={{
              fontSize: "0.9rem",
              fontWeight: 600,
              color: "var(--text-primary)",
            }}
          >
            Submission Status: Pending Recruiter Review
          </span>
        </div>

        <div
          style={{
            background: "rgba(59, 130, 246, 0.06)",
            border: "1px solid rgba(59, 130, 246, 0.15)",
            padding: "14px",
            borderRadius: "10px",
            marginBottom: "28px",
            fontSize: "0.85rem",
            color: "var(--text-muted)",
            lineHeight: 1.6,
          }}
        >
          <ClipboardCheck
            size={18}
            style={{
              display: "inline",
              verticalAlign: "middle",
              marginRight: "7px",
            }}
          />
          Your score and qualification decision will remain
          confidential until the recruiter completes the review.
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: "12px",
            flexWrap: "wrap",
          }}
        >
          <button
            onClick={() =>
              navigate("/candidate/first-round-assessments")
            }
            className="btn btn-outline"
          >
            <ClipboardCheck size={16} />
            My Assessments
          </button>

          <button
            onClick={() => navigate("/candidate/dashboard")}
            className="btn btn-primary"
          >
            Go to Dashboard
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}