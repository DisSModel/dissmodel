// Accept $...$ for inline math (as well as \(...\)) in notebook markdown cells.
window.MathJax = {
  tex: {
    inlineMath: [["$", "$"], ["\\(", "\\)"]],
    displayMath: [["$$", "$$"], ["\\[", "\\]"]],
    processEscapes: true
  },
  options: { skipHtmlTags: ["script", "noscript", "style", "textarea", "pre", "code"] }
};
