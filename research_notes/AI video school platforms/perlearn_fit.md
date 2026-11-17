# PerLearn fit for AI-video schools

## What is NextGen Schooling / NGEdu publicly?

### Takeaway
NextGen Schooling (also marketed as NG Edu/NGEdu) publicly presents itself as an Australian, curriculum-aligned, AI-assisted homeschooling platform with automated tutoring, interactive/video content, mastery gates, games, assessments, and parent reporting. Public materials support the product identity and feature claims, but not its underlying learner model, video-generation architecture, API surface, customer scale, or measured learning outcomes.

### Cited Findings
- The official site describes NextGen Schooling as an Australian homeschooling platform and advertises “automated tutoring, mastery gates & parent dashboards.” — [NextGen Schooling](https://www.ngedu.com.au/); [Features](https://www.ngedu.com.au/features)
- SkilliHire’s launch announcement identifies NG Edu and NextGen Schooling as the same product, says it was built by SkilliHire, and targets Australian students, parents, schools, and tutors. It lists conversational AI tutors, gamified learning, real-time parent dashboards, AI performance reports, curriculum-aligned interactive videos, weak-concept detection, micro-lesson recommendations, and automatic difficulty adjustment. These are vendor claims, not independently verified outcomes. — [SkilliHire launch announcement](https://www.skillihire.com/blog/ng-edu-ai-homeschooling-australia-launch)
- NextGen’s LinkedIn marketing lists lecture videos, books, assessments, activities, slides, educational games, performance reporting, and “learning by talking to AI.” — [NextGen Schooling LinkedIn post](https://www.linkedin.com/posts/nextgen-schooling-home-school-australia_our-home-schooling-student-shares-her-experience-activity-7493167100396613632-5OZN)
- Its public video-channel listing includes demonstrations framed around mastery rather than task completion, parent reporting, paperless homeschooling, and “Mastery Gateway.” — [NextGen Schooling channel mirror](https://invidious.tiekoetter.com/channel/UCbjg0gNgaY3zQjnFAJB_o_Q)
- The official site publishes privacy and terms pages, but the indexed public text does not expose enough detail to assess data retention, model-provider sharing, security controls, or child-data governance. — [Privacy policy](https://www.ngedu.com.au/privacy); [Terms](https://www.ngedu.com.au/terms)

### Inferences
- NextGen already claims the “what next?” layer: curriculum sequencing, mastery gates, weak-area detection, micro-lessons, and difficulty adjustment.
- The clearest complementary position for PerLearn is therefore not another curriculum sequencer. It is an outcome-measured “how to teach the next explanation” service operating inside or immediately after NextGen’s mastery gate.
- “NGEdu already knows what next; PerLearn learns how to teach it” is directionally credible, but should be presented as an integration hypothesis until NextGen confirms its actual architecture.

### Gaps
- No public developer/API documentation, event schema, webhooks, LMS standards support, or content-generation contract was found.
- No reliable public evidence was found for active family counts, institutional customers, retention, learning gains, funding, or the exact models/vendors used.
- Public pages do not establish whether lecture videos are pre-produced, selected from a library, generated dynamically, or regenerated per learner.

## Integration points on a typical AI-video school stack

### Takeaway
The common public product pattern is source/topic → lesson or video generation/selection → watch → quiz → progress/review. PerLearn fits as a decision-and-evaluation layer around the assessment boundary: consume watch and assessment events, diagnose the likely misconception, select an instructional treatment, parameterize the next video, then score delayed transfer to update the policy.

### Cited Findings
- Ulearn publicly describes a three-step flow: choose a topic, select a real YouTube lesson, then have the child watch and answer video-grounded quiz questions; it also uses spaced review. — [Ulearn](https://www.ulearnai.org/)
- TALA describes topic/notes/documents → review outline → narrated video with quiz and flashcards, with learner level and lesson length as generation controls. — [TALA AI](https://talaai.io/ai-explainer-video-maker)
- Tutro describes input from a question, image, PDF, or link → storyboard and narrated animated lesson → adaptive quiz, with a context-aware tutor available during the video and quiz. — [Tutro](https://tutro.ai/)
- StudyAI describes curriculum planning, lesson notes, quizzes with stored scores, review cards from missed questions, and optional narrated slide lessons for difficult topics. — [StudyAI](https://my-study-ai.com/for/homeschoolers)
- Contextual-bandit research has explicitly modeled prior concept knowledge as context, learning actions such as a video/question/simulation as arms, and future-assessment performance as reward. — [EDM 2016 paper](https://www.educationaldatamining.org/EDM2016/proceedings/paper_18.pdf); [ICASSP 2017 paper](https://doi.org/10.1109/icassp.2017.7953377)
- Knewton’s partner architecture shows the established integration pattern: the host sends content metadata and learner interaction/performance events; the adaptive service estimates knowledge state and returns recommendations and analytics. — [Knewton API overview](https://dev.knewton.com/implementation/api-overview/); [Sending events](https://dev.knewton.com/implementation/sending-events/); [Recommendations](https://dev.knewton.com/implementation/getting-recommendations/)

### Inferences
- A practical insertion map is:
  1. **Before generation:** host sends learner ID/pseudonym, target concept, mastery estimate, prior attempts, known misconception tags, age/grade, language, accessibility constraints, and available method variants.
  2. **Generation control:** PerLearn returns a method choice and structured treatment parameters, e.g. `worked_example`, `problem_first`, `visual`, or `story_analogy`, plus pacing, prerequisite reminder, example context, and prohibited misconceptions.
  3. **During watch:** host logs start/stop, completion, seeks, replays, pauses, tutor questions, captions, speed, and abandonment. These are engagement/context signals, not mastery rewards.
  4. **Immediate evaluation:** replace or augment the static recall quiz with short diagnostic items selected to distinguish misconceptions. Return concept state, misconception probabilities, confidence, and remediation target.
  5. **Next-video decision:** bandit selects a teaching treatment conditioned on concept, mastery bin, prior treatments, and constraints; the host’s generator renders the next video in that form.
  6. **Delayed evaluation:** after spacing and without scaffolds, administer an isomorphic or transfer item. This delayed, unassisted outcome—not watch completion, satisfaction, or same-session practice—is the learning reward.
  7. **Policy/content refinement:** write the delayed outcome back against learner context, content/version ID, method ID, generator/model version, and assessment IDs. Aggregate results inform prompts, templates, and generation QA.
- Minimum interfaces:
  - `POST /diagnose` → misconception/state estimate.
  - `POST /recommend-method` → chosen treatment plus propensity/exploration metadata.
  - `POST /events` → immutable watch, response, hint, generation, and assessment events.
  - `POST /reward` → delayed outcome joined to the original recommendation.
  - Optional batch export → treatment-effect and content-quality reports.
- Essential identifiers are `learner_pseudo_id`, `skill_id`, `concept_version`, `content_id`, `content_version`, `method_id`, `policy_version`, `generator_model_version`, `assessment_item_id`, and `recommendation_id`; without stable versioning, buyers cannot tell whether gains came from method, content quality, model changes, or easier tests.
- The lowest-friction pilot does not require per-learner video rendering. Generate four approved variants for one skill, randomize/explore among them, and update method selection from delayed checks. Dynamic generation can follow after the treatment effect is credible.

### Gaps
- Public competitor pages describe flows, not production data contracts, latency budgets, moderation pipelines, or video-rendering costs.
- Watch telemetry may correlate with confusion but does not identify mastery or causally prove that a teaching method worked.

## Where PerLearn sits and what it should own

### Takeaway
PerLearn should sit after the first content exposure and at the mastery gate, augmenting—not blindly replacing—the host quiz. It should own misconception-aware diagnostics, treatment selection, delayed reward attribution, and the feedback signal to the video generator; the host should retain curriculum scope, sequencing, rendering, delivery, identity, and parent-facing records.

### Cited Findings
- PerLearn’s public project description defines its live flow as adaptive diagnostic → contextual bandit method choice → verified lesson → delayed unassisted check → parent summary, with four treatments: worked example, problem first, visual explanation, and real-world story/analogy. — [PerLearn README](https://github.com/Azhartula/Per_learn)
- The project explicitly uses delayed unassisted checks to train the bandit and uses symbolic verification for numeric answers in its Year 5 fractions demo. — [PerLearn README](https://github.com/Azhartula/Per_learn)
- Research on assessment-informed personalization reports that assessment data can improve instruction when it is translated into actionable, individualized teaching recommendations; the reviewed literacy system reported effects of roughly 0.2–0.4 per school year across seven randomized trials, though this evidence is domain-specific and does not validate PerLearn’s exact methods. — [Connor et al., 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC5854500/)
- The educational contextual-bandit literature supports the formal structure of selecting learning actions from knowledge-state context and evaluating them on later assessment. One real-world dataset study reported about 10% more assessment credit than random action selection, but it did not test PerLearn’s four video styles. — [EDM 2016 paper](https://www.educationaldatamining.org/EDM2016/proceedings/paper_18.pdf)
- ASSISTments’ APLS uses bandits as a modular support-selection service; its initial Beta-Bernoulli Thompson Sampling was only slightly better than random, while a decision-tree contextual method showed up to 10% simulated improvement and was being deployed. This is evidence both for feasibility and for modest/uncertain gains. — [Automatic Interpretable Personalized Learning](https://doi.org/10.1145/3491140.3528267)
- Rigorous reviews do not support labeling learners as fixed “visual” or “auditory” types and matching instruction to a preference quiz. A 2024 meta-analysis found a small aggregate matched-instruction effect, but only 26% of outcomes showed the required crossover and study quality was weak, so the authors advised against widespread adoption. — [Mini-review](https://pmc.ncbi.nlm.nih.gov/articles/PMC6113575/); [2024 meta-analysis](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2024.1428732/full)

### Inferences
- Recommended product boundary:
  - **Host owns WHAT:** standards graph, syllabus, prerequisites, next concept, schedules, identity, video renderer/player, parent dashboard.
  - **PerLearn owns HOW:** diagnostic item selection, misconception state, treatment policy, exploration limits, delayed reward, and generation instructions.
  - **Shared:** safety rules, content QA, experiment governance, and reporting.
- “Instead of a static quiz” should be softened to “replace or augment the static end quiz with a diagnostic mastery gate.” Platforms still need conventional scored evidence for reporting, compliance, and comparability.
- Immediate quiz data should update misconception/mastery beliefs; only a later unassisted transfer check should update the teaching-method reward. This reduces practice leakage and avoids rewarding a method merely because its example resembles the test.
- The learner model should say “method X has worked best for this learner, concept, and mastery state so far,” not “this child is a visual learner.” Method effects can change with expertise, topic, accessibility needs, and content quality.
- For video generation, PerLearn should return structured controls rather than raw prose alone: instructional sequence, number/type of examples, visual schema, narration density, misconception to contrast, retrieval prompt, practice transition, duration range, and safety constraints.

### Gaps
- PerLearn’s current headline simulation uses demo-scaled method effects and is not evidence of real child learning gains.
- No study found directly validates the exact four-method taxonomy, delayed reward interval, mastery bins, or video-specific generation controls.
- The best delay and transfer-item design will vary by age, subject, and platform cadence and requires prospective testing.

## Competitive alternatives

### Takeaway
Most established alternatives optimize content/topic/difficulty selection or provide interactive tutoring. PerLearn’s defensible wedge is narrower: experimentally choose the explanatory treatment used to generate the next lesson and attribute delayed mastery to that treatment. This is complementary to incumbents, but they could build it if the distinction proves valuable.

### Cited Findings
- Knewton builds a knowledge graph linking content to concepts and prerequisites, ingests graded events, estimates granular knowledge state, and recommends instructional or assessment modules toward a goal. Incorrect answers increase the likelihood of similar or prerequisite content. — [Knewton API overview](https://dev.knewton.com/implementation/api-overview/); [Recommendations](https://dev.knewton.com/implementation/getting-recommendations/); [Sending events](https://dev.knewton.com/implementation/sending-events/)
- Duolingo’s Birdbrain estimates learner proficiency and exercise difficulty, predicts correctness, and helps its session generator select appropriately difficult exercises. Duolingo also adapts difficulty within a lesson and uses A/B testing to evaluate changes. — [Birdbrain](https://blog.duolingo.com/learning-how-to-help-you-learn-introducing-birdbrain/); [Adaptive lessons](https://blog.duolingo.com/keeping-you-at-the-frontier-of-learning-with-adaptive-lessons/)
- Khan Academy describes Khanmigo as a 24/7 Socratic tutor that guides with prompts rather than giving answers; it can identify mistakes/misconceptions and provide context-aware help for videos. — [Khanmigo access](https://blog.khanacademy.org/ai-tutor-tutoring-khanmigo-kl/); [Khanmigo overview](https://blog.khanacademy.org/sal-khans-2023-ted-talk-ai-in-the-classroom-can-transform-education/)
- Tutro already claims narrated generated lessons, adaptive quizzes, progress tracking, and alternate spoken explanations during video playback. — [Tutro](https://tutro.ai/)

### Inferences
- **Knewton-like sequencing:** strongest at “which concept/resource next?” PerLearn can consume its mastery state and choose how the selected resource is expressed.
- **Duolingo-like difficulty:** strongest at “how hard should the next exercise be?” PerLearn’s method choice is orthogonal if difficulty is held constant.
- **Khanmigo/Socratic chat:** strongest at interactive, in-the-moment scaffolding. PerLearn is a policy and measurement layer for asynchronous generated lessons; a Socratic treatment could later become another arm.
- **Native AI-video adaptivity:** Tutro and similar products are the closest strategic threat because they already control generation, quizzes, and telemetry. PerLearn needs evidence, clean integration, interpretable reports, and faster experimentation—not merely the claim that it personalizes.
- Competitive positioning should avoid “we personalize learning,” which all four categories claim. Use: “Your stack selects the next skill and difficulty. PerLearn runs a controlled learning loop to discover which explanation treatment produces later, unassisted mastery, then sends that treatment back to your generator.”

### Gaps
- Public materials do not reveal whether these competitors already run hidden treatment-level bandits over explanation format.
- No comparable public benchmark measures delayed transfer across generated video treatments.

## Honest risks and objections from platform buyers

### Takeaway
The largest objections are evidentiary and operational: uncertain incremental lift, cold start/exploration on children, confounding between “method” and content quality, assessment burden, render cost/latency, safety and privacy, and loss of product control. A bounded, pre-generated, holdout-based pilot is more credible than asking a buyer to replace its adaptive stack.

### Cited Findings
- The ASSISTments APLS paper reports that an initial Thompson-sampling approach was only slightly better than random, demonstrating that a bandit architecture alone does not guarantee meaningful gains. — [Automatic Interpretable Personalized Learning](https://doi.org/10.1145/3491140.3528267)
- A 38-class ManyClasses study found no general advantage of immediate versus delayed feedback, so “delayed” should not be marketed as universally superior; PerLearn’s delayed check is primarily an attribution/retention measure, not a claim that delayed feedback itself is always better. — [Fyfe et al., 2021](https://journals.sagepub.com/doi/full/10.1177/25152459211027575)
- UNESCO warns that GenAI education products raise child-data privacy, age-appropriateness, validation, and human-oversight concerns; it recommends privacy protection and age limits for independent use. — [UNESCO guidance](https://www.unesco.org/en/articles/guidance-generative-ai-education-and-research)
- Khan Academy publicly emphasizes content not being used to train underlying models, moderation, adult visibility, safety alerts, and FERPA/COPPA controls, illustrating the procurement baseline buyers may expect. — [Khan Academy district partnership](https://blog.khanacademy.org/empowering-new-york-state-educators-to-unlock-mastery-learning-with-ai-powered-solutions-from-khan-academy/)
- Reviews warn that matching instruction to presumed learning styles is poorly supported and costly, creating reputational risk if PerLearn is framed as discovering a child’s fixed style. — [Mini-review](https://pmc.ncbi.nlm.nih.gov/articles/PMC6113575/); [2024 meta-analysis](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2024.1428732/full)

### Inferences
- Likely buyer objections and credible responses:
  - **“We already personalize.”** Show that their model chooses topic/difficulty while PerLearn estimates treatment effects. Integrate with, rather than replace, their mastery model.
  - **“Where is the real-world evidence?”** Admit the current simulator is a demo. Offer a preregistered pilot with delayed transfer, fixed content QA, a baseline policy, and confidence intervals.
  - **“Exploration can give a child a worse lesson.”** Use safety-constrained exploration: approved variants only, cap regret, fall back after failure, exclude high-stakes/remedial cases, and allow parent/teacher override.
  - **“You are reinventing learning styles.”** Never label a child. Model learner × concept × mastery-state × treatment interactions and allow preferences to drift.
  - **“Your reward is noisy.”** Use multiple isomorphic items, spacing windows, propensity logging, missingness handling, and periodic randomized holdouts. Report uncertainty, not a deterministic “best style.”
  - **“Generated variants differ in more than method.”** Apply shared learning objectives, facts, duration, vocabulary, examples, difficulty, and assessment blueprint; version every artifact; audit samples; use symbolic or rule-based verification where possible.
  - **“More quizzes hurt engagement.”** Keep diagnostics short, embed one or two discriminating items, reuse required mastery checks, and schedule delayed checks inside normal review.
  - **“Per-user video generation is slow and expensive.”** Begin with cached/pre-generated method variants; generate asynchronously; render only when the expected value exceeds cost; reuse safe scene templates.
  - **“We cannot send child data to another vendor.”** Support pseudonymous IDs, data minimization, regional storage, short retention, deletion/export, no model training on customer data, subprocessor disclosure, encryption, audit logs, and a clear controller/processor contract.
  - **“This makes our system harder to explain.”** Return recommendation reason, confidence, alternatives, and policy version; expose parent/teacher-readable language such as “a worked example improved later fraction transfer twice,” not psychometric labels.
  - **“Vendor lock-in/product control.”** Keep content and learner identity in the host; offer schema-based recommendations and event ingestion; make policy output inspectable and reversible.
  - **“Optimization could game the metric.”** Track a balanced scorecard: delayed mastery/transfer first, plus time, abandonment, hint use, equity gaps, and adverse-content flags. Do not optimize completion alone.
- Pilot design most likely to pass procurement:
  1. One subject, one age band, 3–5 skills, and four human-approved or pre-generated variants.
  2. PerLearn runs in shadow mode first to validate event joins and estimate sample size.
  3. Randomized baseline versus constrained contextual policy; difficulty and curriculum sequencing remain controlled by the host.
  4. Primary outcome is delayed unassisted transfer; guardrails include completion, distress/abandonment, subgroup performance, factual-error rate, and generation cost.
  5. Promote to dynamic generation only if lift survives holdout evaluation and content/safety review.

### Gaps
- No public data provides the traffic, render economics, assessment cadence, or learner age mix needed to size an NGEdu-specific pilot.
- Legal requirements depend on deployment jurisdiction and buyer role; UNESCO guidance is not a substitute for Australian privacy/education counsel.
- Sample-size and time-to-learn estimates require baseline mastery rates, expected treatment lift, learner clustering, and repeat-measure structure.
