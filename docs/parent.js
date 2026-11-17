(function () {
  const METHOD_PLAIN = {
    worked_example: "Worked examples first",
    problem_first: "Problem first",
    visual: "Visual explanations",
    story_analogy: "Stories & analogies",
  };

  const SKILL_LABELS = {
    equivalent_fractions: "Equivalent fractions",
    ordering_fractions: "Ordering fractions",
    add_subtract_fractions: "Add & subtract",
    multiply_fractions: "Multiply fractions",
    fraction_of: "Fraction of a quantity",
    mixed_improper: "Mixed & improper",
  };

  const MISC = {
    bigger_denominator_bigger: "Thinks a bigger denominator means a bigger fraction",
    add_across: "Adds numerators and denominators separately",
    ignore_denominator: "Compares only numerators when denominators differ",
    multiply_add_confusion: "Multiplies fractions by adding instead",
    of_means_divide_wrong: "Treats “fraction of” as divide by numerator",
    equivalent_add_same: "Makes equivalents by adding the same to num and den",
  };

  const data = window.PERLEARN_SESSION;
  if (!data) {
    document.getElementById("session-meta").textContent = "No session data found.";
    return;
  }

  const d = data.diagnostic;
  const methodPlain = METHOD_PLAIN[data.method] || data.method;
  const weak = SKILL_LABELS[d.weakest_skill] || d.weakest_skill;
  const why =
    (data.lesson && data.lesson.misconception_id && MISC[data.lesson.misconception_id]) ||
    (d.active_misconceptions || []).map((m) => MISC[m] || m).slice(0, 2).join("; ") ||
    "No clear misconception tagged";

  document.getElementById("student-title").textContent =
    "Session for " + (data.student_name || "Student");
  document.getElementById("session-meta").textContent =
    "Live loop demo · " + (data.created_at || "").replace("T", " ").slice(0, 19) + " UTC";
  document.getElementById("method-value").textContent = methodPlain;
  document.getElementById("diag-value").textContent =
    d.n_correct + "/" + d.n_items + " · " + Math.round(d.ability * 100) + "%";
  document.getElementById("delay-value").textContent =
    Math.round((data.delayed.score || 0) * 100) + "%";
  document.getElementById("weak-skill").textContent = weak;
  document.getElementById("why-text").textContent = why;
  document.getElementById("effort-text").textContent = data.effort_note || "—";
  document.getElementById("lesson-title").textContent =
    (data.lesson && data.lesson.title) || "—";
  document.getElementById("method-plain").textContent =
    "Right now this child learns fastest from " + methodPlain.toLowerCase() + ".";

  const review = document.getElementById("review-tag");
  review.textContent = data.delayed.review_due ? "Review due soon" : "Review not urgent";
  const verify = document.getElementById("verify-tag");
  verify.textContent = data.lesson && data.lesson.all_verified ? "Answers SymPy-verified" : "Verify failed";

  const bars = document.getElementById("skill-bars");
  const scores = d.skill_scores || {};
  Object.keys(scores)
    .sort((a, b) => scores[a] - scores[b])
    .forEach((skill) => {
      const pct = Math.round(scores[skill] * 100);
      const row = document.createElement("div");
      row.className = "skill";
      row.innerHTML =
        '<div class="skill-top"><span>' +
        (SKILL_LABELS[skill] || skill) +
        "</span><span>" +
        pct +
        "%</span></div>" +
        '<div class="bar"><i style="width:' +
        pct +
        '%"></i></div>';
      bars.appendChild(row);
    });
})();
