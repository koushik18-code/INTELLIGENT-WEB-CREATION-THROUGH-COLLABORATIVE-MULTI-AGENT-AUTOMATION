import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { gsap } from "gsap";
import AgentPipeline, { PIPELINE_STEPS } from "../components/AgentPipeline";
import ParticleText from "../components/ParticleText";
import CurvedInput from "../components/CurvedInput";
import TrueFocus from "../components/TrueFocus";
import DotField from "../components/DotField";
import FallingText from "../components/FallingText";
import ElasticMesh from "../components/ElasticMesh";
import BorderGlow from "../components/BorderGlow";
import { useScrollReveal } from "../animations/useScrollReveal";
import "./Landing.css";

const STORY = [
  {
    n: "01",
    title: "Describe",
    body: "Tell it what you want to build — a portfolio, a product launch, a restaurant site. Plain language is enough.",
  },
  {
    n: "02",
    title: "Understand",
    body: "The Requirements Agent reads your brief and turns it into a concrete, structured plan for what the site needs to do.",
  },
  {
    n: "03",
    title: "Design",
    body: "The UI/UX Agent works out the visual direction — layout, hierarchy, tone — before a line of code is written.",
  },
  {
    n: "04",
    title: "Architect",
    body: "The Architecture Agent decides how the site is structured: pages, sections, and the files that will hold them.",
  },
  {
    n: "05",
    title: "Create",
    body: "Content and Code agents write real copy and real HTML, CSS, and JavaScript — a working site, not a mockup.",
  },
  {
    n: "06",
    title: "Test",
    body: "The Testing Agent checks the generated site for broken markup, missing assets, and accessibility basics.",
  },
  {
    n: "07",
    title: "Refine",
    body: "If anything fails, Debugging and Quality agents iterate automatically until the result holds up.",
  },
  {
    n: "08",
    title: "Launch",
    body: "Preview it live, ask for changes in plain language, and export a clean, ready-to-host ZIP when you're happy.",
  },
];

function useDemoPipeline() {
  const [statuses, setStatuses] = useState({});

  useEffect(() => {
    let i = 0;
    let cancelled = false;
    const order = PIPELINE_STEPS.map((s) => s.key);

    function step() {
      if (cancelled) return;
      const key = order[i % order.length];
      const prevKey = order[(i - 1 + order.length) % order.length];
      setStatuses((prev) => {
        const next = { ...prev, [key]: "running" };
        if (i > 0) next[prevKey] = "done";
        if (i === 0) {
          // Starting a fresh loop — clear previous completions.
          order.forEach((k) => { next[k] = k === key ? "running" : "pending"; });
        }
        return next;
      });
      i += 1;
      const delay = i % order.length === 0 ? 1800 : 900;
      setTimeout(step, delay);
    }
    const t = setTimeout(step, 600);
    return () => { cancelled = true; clearTimeout(t); };
  }, []);

  return statuses;
}

export default function Landing() {
  const heroRef = useRef(null);
  const navigate = useNavigate();
  useScrollReveal(".scroll-reveal");
  const demoStatuses = useDemoPipeline();

  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion || !heroRef.current) return;
    const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
    tl.fromTo(".hero-eyebrow", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.6 })
      .fromTo(".hero-title", { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.9 }, "-=0.3")
      .fromTo(".hero-sub", { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.7 }, "-=0.5")
      .fromTo(".hero-ctas", { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.6 }, "-=0.4")
      .fromTo(".hero-orbit", { opacity: 0, scale: 0.92 }, { opacity: 1, scale: 1, duration: 1.1 }, "-=0.7");
  }, []);

  return (
    <div className="landing">
      <section className="hero" ref={heroRef}>
        <div className="hero-dot-field" aria-hidden="true">
          <DotField
            dotRadius={1.35}
            dotSpacing={15}
            bulgeStrength={52}
            glowRadius={150}
            gradientFrom="rgba(168, 85, 247, 0.28)"
            gradientTo="rgba(180, 151, 207, 0.12)"
            glowColor="#0b0a10"
          />
        </div>
        <div className="container hero-grid">
          <div>
            <p className="eyebrow hero-eyebrow">Multi-agent website generation</p>
            <h1 className="hero-title">Build websites<br />with AI.</h1>
            <p className="hero-sub">
              A team of specialized agents — Requirements, UI/UX, Architecture, Content, Code,
              Testing, Debugging, and Quality — work together to plan, design, generate, test,
              and refine a real website from a single description.
            </p>
            <div className="hero-ctas">
              <Link to="/builder" className="btn btn-primary">Start Building</Link>
              <a href="#how-it-works" className="btn">See How It Works</a>
            </div>
          </div>
          <div className="hero-orbit" aria-label="AI-generated websites form from ideas">
            <ParticleText
              text="BUILD"
              particleSize={2}
              density={4}
              color="#f5f5f5"
              highlightColor="#c7a6ff"
              scatter={150}
              gatherDuration={1500}
              stagger={360}
              pointerRepel={34}
              repelRadius={110}
              idleDrift={0.65}
              trigger="hover"
              fontSize="clamp(4rem, 13vw, 8rem)"
              fontWeight={800}
              glow
            />
          </div>
        </div>
      </section>

      <section id="how-it-works" className="story">
        <div className="container">
          <p className="eyebrow scroll-reveal">How it works</p>
          <div className="story-list">
            {STORY.map((s) => (
              <div className="story-row scroll-reveal" key={s.n}>
                <span className="story-n">{s.n}</span>
                <div>
                  <h3 className="story-title">{s.title}</h3>
                  <p className="story-body">{s.body}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="story-falling scroll-reveal">
            <FallingText
              text="Describe your idea and watch the agents bring it to life."
              highlightWords={["idea", "agents", "life."]}
              highlightClass="story-falling-highlight"
              trigger="scroll"
              backgroundColor="transparent"
              gravity={0.8}
              fontSize="1.05rem"
            />
          </div>
        </div>
      </section>

      <section className="pipeline-demo">
        <div className="container pipeline-demo-grid">
          <div className="scroll-reveal">
            <p className="eyebrow">The agent pipeline</p>
            <h2 className="pipeline-demo-title"><TrueFocus sentence="Eight agents" borderColor="#c7a6ff" glowColor="rgba(199, 166, 255, 0.55)" animationDuration={0.45} pauseBetweenAnimations={1.2} /><br />One coherent result.</h2>
            <p className="pipeline-demo-copy">
              Every generation runs through the same disciplined pipeline — no agent talks to
              another directly. An orchestrator sequences the work, so the process is
              inspectable and repeatable every time.
            </p>
          </div>
          <div className="pipeline-demo-visual scroll-reveal">
            <div className="pipeline-mesh" aria-hidden="true">
              <ElasticMesh
                color1="#21152f"
                color2="#8b5cf6"
                highlight="#f5f5f5"
                showGrid
                gridDensity={18}
                gridOpacity={0.16}
                resolution={18}
                interaction="hover"
                tilt={10}
                shading={0.42}
              />
            </div>
            <div className="pipeline-agent-layer">
              <AgentPipeline statuses={demoStatuses} />
            </div>
          </div>
        </div>
      </section>

      <section className="final-cta">
        <div className="container final-cta-inner scroll-reveal">
          <h2>Ready to build something?</h2>
          <BorderGlow
            className="cta-glow"
            glowColor="275 80 78"
            backgroundColor="#15121b"
            borderRadius={26}
            glowRadius={32}
            glowIntensity={0.8}
            colors={["#c084fc", "#8b5cf6", "#38bdf8"]}
          >
            <CurvedInput
              placeholder="Describe the site you want to build"
              buttonText="Start building"
              theme="dark"
              bend={22}
              width="min(560px, 100%)"
              onSubmit={(value) => navigate("/builder", { state: { prompt: value } })}
            />
          </BorderGlow>
          <Link to="/builder" className="btn btn-primary">Start Building</Link>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="container footer-inner">
          <span>AI Website Builder</span>
          <span className="muted">Generated sites run in a sandboxed preview. Your API keys never leave the server.</span>
        </div>
      </footer>
    </div>
  );
}
