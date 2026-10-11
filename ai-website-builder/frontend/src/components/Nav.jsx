import { Link, useLocation } from "react-router-dom";
import "./Nav.css";

export default function Nav() {
  const location = useLocation();
  return (
    <header className="nav">
      <div className="nav-inner container">
        <Link to="/" className="nav-mark">AI Website Builder</Link>
        {location.pathname === "/" && (
          <nav className="nav-links">
            <a href="#how-it-works">How it works</a>
            <Link to="/builder" className="btn btn-primary nav-cta">Start Building</Link>
          </nav>
        )}
        {location.pathname !== "/" && (
          <Link to="/" className="nav-back">← Home</Link>
        )}
      </div>
    </header>
  );
}
