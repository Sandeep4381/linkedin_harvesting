# JD and AI resume workflow

`python recruit.py --jobs-only` discovers all Active/Open jobs across list pages,
then opens their detail pages one by one. Use `--jobs-limit 25` to limit discovery.
During normal runs, each job is queued immediately when `analysis_status` becomes
`completed`. The LinkedIn consumer processes it while the producer continues
analyzing other jobs on its separate Ceipal tab. Jobs run in readiness order;
the consumer no longer waits for all analysis to finish. `--jobs-only` continues
to collect/analyze jobs without starting LinkedIn processing.
At startup, cached jobs with `analysis_status=completed` enter the LinkedIn queue
before job discovery. Completed analysis is reused regardless of analysis version;
it is never sent to AI again automatically. In `extract_job.json`,
`linkedin_processing` progresses from `pending` to `processing` to `completed`.
Completion follows the existing job history check: all location passes and all
collected profiles must be final. Errors/incomplete jobs return to `pending`;
interrupted `processing` jobs resume from history on restart. Jobs already marked
`completed` are skipped. Search-only runs do not mark applicant work complete.
Existing jobs missing `job_analysis_version` are enriched on the next eligible run.
Completed jobs remain skipped.

`extract_job.json` stores original `title`, `cleaned_title`, `jd`,
`job_description`, `skills` (up to seven, aiming for five to seven when supported),
`city`, `state`, `country`, `location`, `location_details` and `location_variants`.
Location analysis reads the listing together with the JD. The variants retain the
existing full location, state/country and country search sequence.
Set `CEIPAL_JOB_DESCRIPTION_SELECTOR` when a page needs a specific JD container;
otherwise the collector clicks `a.cpjDS.show_all_desc` (Original Format), expands
More when available, and reads `.jd_expand_div_data` or the complete `#descmore`.
It never reads the truncated `#descless` as the JD. Version 1 job analyses are
refreshed on the next eligible run. Version 3 reads and prints raw title, location
and full JD before any AI request, and persists `raw_title`, `raw_location` and
`raw_jd` first. AI errors are stored in `analysis_error`; extracted data survives
an Azure failure. A hidden Original Format link is skipped when the full JD is
already present in the page.

Normal runs use local Ollama for structured profile extraction
and resume content, then render the result with the existing HTML/PDF template.
Missing facts must remain missing; job skills are never added to candidate skills.
The main pipeline selects its provider from `.env`: `AI_PROVIDER=ollama` uses
Ollama (`qwen2.5:3b` by default) without an API key. `AI_PROVIDER=azure_ai` uses
Azure with `AZURE_AI_ENDPOINT` (the complete chat completions URL including
deployment and api-version) and `AZURE_AI_API_KEY`. Choose one provider per run;
restart the script after editing `.env`. Job analysis, resume extraction and
location validation all use this selection.
Set `OLLAMA_URL=http://localhost:11434/api/chat` and `AI_PROVIDER=ollama`.
Start Ollama with `ollama serve` if it is not already running.

After Ceipal parses the resume, Canada business units keep or select Canada and
map the job province to the form's full-name or abbreviated province option.
For every business unit the actual parsed city/state/country is AI-validated
immediately before saving. Missing or invalid locations block that applicant's
save; non-Canada locations are not overwritten with job locations.

Offline checks: `python -m unittest discover`.
Live selector behavior and dependent dropdown loading require a Ceipal session.

Location searches now run as a collection phase: full location, state/country,
then country, saving each pass's URLs with `search_status=completed` and
`status=collected`. After every variant has been searched, all URLs are combined
and deduplicated before candidate extraction/resume/upload starts. `--limit`
limits collection per variant; the final combined list is processed in full.
Existing stored pass URLs are reused on restart so remaining variants run first.

Before building a resume, `profile_location.py` validates extracted geography using
`pycountry` for country/subdivision normalization and `geopy` with Nominatim for
city/state/country matching. Only the city/state/country query is sent to the
geocoder, not the candidate name, profile URL or resume. Calls are serialized,
spaced and cached. Set `GEOCODER_DOMAIN` to use another Nominatim-compatible host.
Install the added dependencies with `python -m pip install -r requirements.txt`.

A valid match maps canonical values to `profile.location`, `profile.city`,
`profile.state` and `profile.country`, used by the PDF renderer. The validation
result is retained as `location_validation` in `profile_data.json` and reused
when those fields are unchanged. Missing, invalid or ambiguous profile locations
and geocoder failures use the job's available city/state/country for the resume
and Ceipal form. Missing job components stay empty. `location_source=job_fallback`
records this choice, and `extracted_profile_location` preserves the original
candidate location; the fallback is not marked as a verified candidate location.
Actual form-control errors can still stop saving. This validates geographic
consistency, not where the candidate actually resides.

After successful Ceipal parsing, the pre-save check now validates only whether
the parsed/profile/job city is a real city name. It keeps a valid parsed city;
otherwise it tries the profile and AI-final job city. Canada business units keep
an already selected Canada country or select Canada, then try the job's province
dropdown using its name or abbreviation. Missing/unmatched location controls are
logged without treating the resume as a parser failure. A later form/save error
retains the PDF, keeps the job incomplete and never writes parser-failed completion.
