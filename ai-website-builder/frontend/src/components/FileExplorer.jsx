import { useEffect, useMemo, useState } from "react";
import hljs from "highlight.js/lib/core";
import xml from "highlight.js/lib/languages/xml";
import css from "highlight.js/lib/languages/css";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import "highlight.js/styles/atom-one-dark.css";
import "./FileExplorer.css";

hljs.registerLanguage("html", xml);
hljs.registerLanguage("css", css);
hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("json", json);
hljs.registerLanguage("markdown", markdown);

function Tree({ node, depth, selectedPath, onSelect }) {
  const [open, setOpen] = useState(true);
  if (!node) return null;
  if (node.is_dir) {
    return (
      <div>
        {node.path && (
          <button
            type="button"
            className="tree-row tree-dir"
            style={{ paddingLeft: 10 + depth * 14 }}
            onClick={() => setOpen((o) => !o)}
          >
            <span className={`tree-caret ${open ? "open" : ""}`}>›</span>
            {node.name}
          </button>
        )}
        {open && node.children.map((child) => (
          <Tree key={child.path || child.name} node={child} depth={node.path ? depth + 1 : depth}
                selectedPath={selectedPath} onSelect={onSelect} />
        ))}
      </div>
    );
  }
  return (
    <button
      type="button"
      className={`tree-row tree-file ${selectedPath === node.path ? "active" : ""}`}
      style={{ paddingLeft: 10 + depth * 14 + 16 }}
      onClick={() => onSelect(node.path)}
    >
      {node.name}
    </button>
  );
}

export default function FileExplorer({ tree, selectedPath, content, language, onSelect, empty }) {
  const highlighted = useMemo(() => {
    if (!content) return "";
    try {
      if (language && hljs.getLanguage(language)) {
        return hljs.highlight(content, { language }).value;
      }
      return hljs.highlightAuto(content).value;
    } catch {
      return content;
    }
  }, [content, language]);

  useEffect(() => {}, []);

  if (empty) {
    return <div className="file-explorer-empty">Generate a website to browse its files here.</div>;
  }

  return (
    <div className="file-explorer">
      <div className="file-tree">
        <Tree node={tree} depth={0} selectedPath={selectedPath} onSelect={onSelect} />
      </div>
      <div className="file-code">
        {selectedPath ? (
          <>
            <div className="file-code-header">{selectedPath}</div>
            <pre className="hljs">
              <code dangerouslySetInnerHTML={{ __html: highlighted }} />
            </pre>
          </>
        ) : (
          <div className="file-code-empty">Select a file to view its contents.</div>
        )}
      </div>
    </div>
  );
}
