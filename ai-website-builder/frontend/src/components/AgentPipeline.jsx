import "./AgentPipeline.css";

export const PIPELINE_STEPS = [
  { key: "requirements", label: "Requirements" },
  { key: "ui_ux", label: "UI/UX" },
  { key: "architecture", label: "Architecture" },
  { key: "content", label: "Content" },
  { key: "code_gen", label: "Code" },
  { key: "testing", label: "Testing" },
  { key: "debugging", label: "Debugging" },
  { key: "quality", label: "Quality" },
];

/**
 * `statuses`: { [stepKey]: "pending" | "running" | "done" | "failed" }
 * Renders a vertical line of nodes with a connecting spine — deliberately
 * not a boxes-and-arrows flowchart.
 */
export default function AgentPipeline({ statuses = {}, orientation = "vertical", steps = PIPELINE_STEPS }) {
  return (
    <div className={`pipeline pipeline-${orientation}`}>
      <div className="pipeline-spine" aria-hidden="true" />
      {steps.map((step, i) => {
        const state = statuses[step.key] || "pending";
        return (
          <div key={step.key} className={`pipeline-node state-${state}`} style={{ "--i": i }}>
            <span className="pipeline-dot" />
            <div className="pipeline-copy">
              <span className="pipeline-label">{step.label}</span>
              <span className="pipeline-state">
                {state === "pending" && "Waiting"}
                {state === "running" && "In progress"}
                {state === "done" && "Complete"}
                {state === "failed" && "Needs attention"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
