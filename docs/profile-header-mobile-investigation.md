# PR #79 mobile geometry investigation — 16–18 November 2026

## Finding and evidence boundaries

The geometry helper compared viewport rectangles captured at different times. Global `html { scroll-behavior: smooth }` permits viewport movement after the 180 ms page entrance animation finishes. `document.getAnimations()` does not report scrolling. The original helper read the cover once, then awaited separate browser calls for each control. A control could therefore be compared against a stale cover boundary. No responsive CSS defect was demonstrated; application CSS/components, backend behavior and permissions are unchanged.

The original 15 November failure was expected y >= -474, actual -482 at 390px. It had no synchronized geometry trace, so its exact historical frame cannot be reconstructed. In this investigation, the unchanged scenario passed 10 times; passive instrumentation then passed 50 times; 10 further instrumented measurements also passed. This is an intermittent failure, not a claimed deterministic reproduction of the original run.

A **controlled smooth-scroll replay after the actual Org Chart navigation** reproduced the same strict assertion failure in 2 of 5 runs. The replay explicitly starts smooth scrolling; it is labelled separately from unchanged navigation. It established the measurement defect without changing CSS or relaxing assertions. Same-frame name, badge and identity clearances stayed 72, 75 and 56px respectively throughout the captured frames. Fonts were loaded, the synthetic fixture used initials/gradient with no profile images, and the page entrance animation was finished. The avatar remained the sole overlapping element. Long-name wrapping, images and other widths are tested separately by the existing matrix.

## Measured failure

Viewport 390 × 1000 CSS px, device scale factor 1, Chromium. Navigation reached `/employees/synthetic-person`. At t=1153.5 ms and scrollY=18, the cover bottom was 191. At t=1210.6 ms and scrollY=101, the badge top was 183. The stale comparison required >=190 and failed. At that second scroll position the actual cover bottom was 108, so the badge remained 75px below it. The 83px scroll displacement explains the apparent overlap.

Representative captured rectangles at scrollY=299 (top/bottom, left/right):

| Element | Top | Bottom | Left | Right |
|---|---:|---:|---:|---:|
| Cover | -218 | -90 | 17 | 373 |
| Employee name | -18 | 14 | 37 | 220.48 |
| Status badge | -15 | 11 | 228.48 | 289.19 |
| Identity | -34 | 58 | 37 | 353 |
| Avatar | -130 | -50 | 37 | 117 |
| Provision access | 74 | 114 | 37 | 224.52 |
| Link existing | 122 | 162 | 37 | 195.02 |
| Edit employee | 170 | 210 | 37 | 206.59 |

[Failure screenshot](profile-header-evidence/mobile-investigation/scroll-replay-failure.png) · [Timestamped geometry and frame evidence](profile-header-evidence/mobile-investigation/measured-scroll-replay.json). Screenshots are captured by Playwright on failure while scrolling can continue; use the timestamped rectangles for the exact assertion-time comparison. Data is synthetic only.

## Test-only correction

`geometry.js` waits for fonts and image decoding, then requires three unchanged animation-frame samples with no relevant running header/ancestor animation. Every cover, identity, avatar, action, tab and child-control rectangle is captured together in one browser evaluation. Strict cover-boundary, avatar, noncollision, tabs, background and page-width assertions remain. The existing one-pixel tolerance is unchanged.

The wait is bounded to five seconds, including font/image readiness. On expiry it reports elapsed time, URL, viewport/DPR, stable-frame count, fonts/images, running animations, previous/current rectangles and scroll coordinates. The timeout is a failure boundary, not a delay; no arbitrary sleep or increased test timeout was introduced. Pending settling stops after cancellation.

`compat.spec.js` adds the previously local-only real Org Chart component → Employee Details synthetic navigation at 390/1440px to the existing remote header suite. A smooth-scroll regression verifies valid geometry, then deliberately moves identity above the cover and requires the specific geometry assertion to fail. A separate infinite-animation negative control requires the bounded diagnostic error (200ms test budget). The negative controls cannot pass merely because any unrelated timeout occurred.

## Validation

Final bounded-helper validation:

- Full header suite: **27 passed**, including six viewport widths, content/branding variants, direct Employee Details, My Profile, actions/tabs, native 125/150/200% zoom, chart navigation and both negative controls.
- Formerly failing 390px navigation: **30/30 passed** in an isolated final run (1.5 minutes). An earlier repeat run was interrupted after 19 cases and is not counted as complete.
- Full frontend unit suite: **242 passed / 77 files**; ESLint passed during the investigation. No application source changed afterward.
- Relevant backend regressions: **30 passed**, covering employee/chart and tenant/access boundaries. No backend source changed.
- Real PostgreSQL 16 concurrency: **2 passed**, including inverse assignments and tenant lock behavior.
- Fresh actual Flask/PostgreSQL/Redis authenticated acceptance: **1 passed** (19.2 seconds), 1,001 synthetic employees/two tenants, MFA, profile/directory/chart navigation, reporting changes, cross-tenant rejection and mobile/keyboard controls. Memory mail and loopback services only.
- Remote CI results and exact published head are recorded in PR #79 after publication; no claim of remote success is made before completion.

 Earlier unbounded draft: 59/60 repetition cases passed, with one desktop navigation timeout before header measurement under concurrent local test load. That was not a cover-boundary failure. A resumed run also found the localhost server stopped after session interruption; it was cancelled and restarted. Neither attempt is represented as a passing validation run.

## Limits and review

This corrects a test measurement defect, not scrolling UX or application styling. Chromium checks are not Safari/iOS or complete screen-reader certification. Existing large-bundle and React warnings remain. No production records, environment variables, deployment policies or infrastructure were changed. Zero additional recurring paid infrastructure. PR #79 must remain open pending explicit merge approval.
