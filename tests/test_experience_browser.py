"""Local HTML regression for the supplied Recruiter experience trigger; no network."""
import contextlib
import io
import os
import unittest
from unittest.mock import patch

import linkedin_search as search

HTML = """
<h2>Years of experience</h2>
<div class="collapsible-facet-wrapper__trigger-label" aria-hidden="true"
     data-test-toggle-label="" onclick="window.triggerClicks++; setTimeout(() => {
       document.querySelector('#popup').style.display='block'; }, 100)">
  Years of experience
</div>
<div style="display:none"><input value="99"><input value="99"><button>Update</button></div>
<div id="popup" style="display:none">
  <h3>Years of experience</h3>
  <div><span>From</span><input type="number" id="from" value="0">
       <span>to</span><input type="number" id="to" value="30">
       <button onclick="window.events.push('update'); document.querySelector('#popup').style.display='none'">Update</button>
  </div>
</div>
<button onclick="window.events.push('search')">Search</button>
<script>window.events=[];window.triggerClicks=0;</script>
"""


class ExperienceBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.skipTest("Playwright not installed")
        self.playwright = await async_playwright().start()
        try:
            self.browser = await self.playwright.chromium.launch(headless=True)
        except Exception:
            await self.playwright.stop()
            self.skipTest("Local Chromium unavailable")
        self.page = await self.browser.new_page()
        await self.page.route("https://local-test.invalid/**", lambda route: route.fulfill(body="<html><body></body></html>", content_type="text/html"))
        await self.page.goto("https://local-test.invalid/")
        await self.page.set_content(HTML)
        self.environment = patch.dict(os.environ, {"LINKEDIN_EXPERIENCE_MIN_SELECTOR": "",
                                                  "LINKEDIN_EXPERIENCE_MAX_SELECTOR": "",
                                                  "LINKEDIN_SEARCH_SUBMIT_SELECTOR": ""})
        self.environment.start()

    async def asyncTearDown(self):
        if hasattr(self, "browser"):
            self.environment.stop()
            await self.browser.close()
            await self.playwright.stop()

    async def test_real_trigger_click_fill_update_then_search(self):
        with contextlib.redirect_stdout(io.StringIO()):
            await search.apply_experience(self.page, "5+ years")
            await search.submit_search(self.page, required=True)
        self.assertEqual(await self.page.locator("#from").input_value(), "5")
        self.assertEqual(await self.page.locator("#to").input_value(), "30")
        self.assertEqual(await self.page.evaluate("window.triggerClicks"), 1)
        self.assertEqual(await self.page.evaluate("window.events"), ["update", "search"])

    async def test_already_open_editor_is_not_toggled_closed(self):
        await self.page.locator("#popup").evaluate("el => el.style.display='block'")
        with contextlib.redirect_stdout(io.StringIO()):
            await search.apply_experience(self.page, "3-7 years")
        self.assertEqual(await self.page.locator("#from").input_value(), "3")
        self.assertEqual(await self.page.locator("#to").input_value(), "7")
        self.assertEqual(await self.page.evaluate("window.triggerClicks"), 0)
        self.assertEqual(await self.page.evaluate("window.events"), ["update"])
    async def test_location_pastes_then_selects_first_owned_suggestion(self):
        await self.page.set_content("""
        <div onclick="document.querySelector('#location').style.display='block'">Candidate geographic locations</div>
        <input id="location" style="display:none" placeholder="Enter a location" role="combobox"
          aria-controls="locations" oninput="setTimeout(() => {document.querySelector('#locations').style.display='block'}, 100)">
        <div role="listbox"><div role="option">Unrelated skill</div></div>
        <ul id="locations" role="listbox" style="display:none">
          <li role="option" onclick="window.chosen=1;document.querySelector('#chip').style.display='block'">Canada</li>
          <li role="option" onclick="window.chosen=2">Canada Other</li>
        </ul>
        <button id="chip" aria-label="Remove Canada" style="display:none">Canada</button>
        <script>window.chosen=0</script>
        """)
        with patch.dict(os.environ, {"LINKEDIN_LOCATION_SELECTOR": "", "LINKEDIN_LOCATION_OPTION_SELECTOR": ""}), \
             contextlib.redirect_stdout(io.StringIO()):
            await search.apply_location_paste(self.page, "Canada")
        self.assertEqual(await self.page.locator("#location").input_value(), "Canada")
        self.assertEqual(await self.page.evaluate("window.chosen"), 1)
        self.assertTrue(await self.page.locator("#chip").is_visible())

    async def test_location_already_open_does_not_toggle_trigger(self):
        await self.page.set_content("""
        <div onclick="throw Error('Do not click an open trigger')">Candidate geographic locations</div>
        <input placeholder="Enter a location" aria-controls="suggestions">
        <ul id="suggestions" role="listbox">
        <li role="option" onclick="document.querySelector('#chip').style.display='block'">Toronto, Ontario, Canada</li>
        </ul>
        <button id="chip" aria-label="Remove Toronto, Ontario, Canada" style="display:none">Toronto</button>
        """)
        with patch.dict(os.environ, {"LINKEDIN_LOCATION_SELECTOR": "", "LINKEDIN_LOCATION_OPTION_SELECTOR": ""}), \
             contextlib.redirect_stdout(io.StringIO()):
            await search.apply_location_paste(self.page, "Toronto, Ontario, Canada")
        self.assertTrue(await self.page.locator("#chip").is_visible())
    async def test_title_existing_ember_input_fills_without_toggling_trigger(self):
        await self.page.set_content("""
        <div onclick="window.badTrigger=true">Job titles or boolean</div>
        <input style="display:none" placeholder="enter a job title or boolean…" role="combobox">
        <div id="ember6527" class="ember-view"><div>
        <input id="typeahead-input-ember6112" class="artdeco-typeahead__input ts-common-typeahead__input"
          placeholder="enter a job title or boolean…" role="combobox"
          onkeydown="if(event.key==='Enter'){document.querySelector('#titlechip').style.display='block'}">
        </div></div>
        <button id="titlechip" aria-label="Remove Project Coordinator" style="display:none">Project Coordinator</button>
        <script>window.badTrigger=false;</script>
        """)
        with patch.dict(os.environ, {"LINKEDIN_JOB_TITLE_SELECTOR": ""}), contextlib.redirect_stdout(io.StringIO()):
            await search.apply_job_title(self.page, "Project Coordinator")
        self.assertEqual(await self.page.locator("#typeahead-input-ember6112").input_value(), "Project Coordinator")
        self.assertFalse(await self.page.locator("#titlechip").is_visible())
        self.assertFalse(await self.page.evaluate("window.badTrigger"))

    async def test_title_pastes_literal_without_selecting_suggestions(self):
        await self.page.set_content("""
        <div onclick="document.querySelector('#title').style.display='block'">Job titles or boolean</div>
        <input id="title" style="display:none" placeholder="enter a job title or boolean…" role="combobox" aria-controls="titles" onkeydown="if(event.key==='Enter'){document.querySelector('#titlechip').style.display='block'}">
        <ul id="titles" role="listbox">
        <li role="option" onclick="window.wrong=true">Other role</li>
        <li role="option" onclick="window.wrong=true">Project Coordinator Senior</li>
        </ul>
        <button id="titlechip" aria-label="Remove Project Coordinator" style="display:none">Project Coordinator</button>
        <script>window.wrong=false;</script>
        """)
        with patch.dict(os.environ, {"LINKEDIN_JOB_TITLE_SELECTOR": ""}), contextlib.redirect_stdout(io.StringIO()):
            await search.apply_job_title(self.page, "Project Coordinator")
        self.assertFalse(await self.page.locator("#titlechip").is_visible())
        self.assertEqual(await self.page.locator("#title").input_value(), "Project Coordinator")
        self.assertFalse(await self.page.evaluate("window.wrong"))
    async def test_title_rerenders_after_paste_without_stale_locator_press(self):
        await self.page.set_content("""
        <input id="rerender-title" placeholder="enter a job title or boolean…" role="combobox"
          oninput="const copy=this.cloneNode();copy.removeAttribute('oninput');copy.value=this.value;this.replaceWith(copy)">
        """)
        with patch.dict(os.environ, {"LINKEDIN_JOB_TITLE_SELECTOR": ""}), contextlib.redirect_stdout(io.StringIO()):
            await search.apply_job_title(self.page, "Project Coordinator")
        self.assertEqual(await self.page.locator("#rerender-title").input_value(), "Project Coordinator")
    async def test_experience_uses_supplied_button_and_aria_controls(self):
        await self.page.set_content("""
        <button class="collapsible-facet-wrapper__trigger" aria-expanded="false"
          aria-controls="collapsible-container-ember6256" data-test-toggle-button
          onclick="this.setAttribute('aria-expanded','true');document.querySelector('#collapsible-container-ember6256').style.display='block'">
          <div class="collapsible-facet-wrapper__trigger-label" aria-hidden="true" data-test-toggle-label>Years of experience</div>
          <div>Total years of work experience</div>
        </button>
        <div id="collapsible-container-ember6256" style="display:none">
          <input type="number" id="from" value="0"><input type="number" id="to" value="30">
          <button onclick="window.updated=true">Update</button>
        </div><script>window.updated=false;</script>
        """)
        with contextlib.redirect_stdout(io.StringIO()):
            await search.apply_experience(self.page, "5+ years")
        self.assertEqual(await self.page.locator("button.collapsible-facet-wrapper__trigger").get_attribute("aria-expanded"), "true")
        self.assertEqual(await self.page.locator("#from").input_value(), "5")
        self.assertTrue(await self.page.evaluate("window.updated"))
    async def test_experience_plus_icon_hover_before_click(self):
        await self.page.set_content("""
        <button class="collapsible-facet-wrapper__trigger" onclick="if(window.hovered){document.querySelector('#editor').style.display='block';window.clicked=true}">
          <li-icon type="plus-icon" style="display:inline-block;width:20px;height:20px"
            onmouseenter="window.hovered=true">+</li-icon>
          <div class="collapsible-facet-wrapper__trigger-label" data-test-toggle-label>Years of experience</div>
        </button>
        <div id="editor" style="display:none">
          <input type="number" id="from" value="0"><input type="number" id="to" value="30">
          <button onclick="window.updated=true">Update</button>
        </div><script>window.hovered=false;window.clicked=false;window.updated=false;</script>
        """)
        with contextlib.redirect_stdout(io.StringIO()):
            await search.apply_experience(self.page, "5+ years")
        self.assertTrue(await self.page.evaluate("window.hovered"))
        self.assertTrue(await self.page.evaluate("window.clicked"))
        self.assertTrue(await self.page.evaluate("window.updated"))
        self.assertEqual(await self.page.locator("#from").input_value(), "5")
    async def test_live_dom_requires_label_click_not_button_centre(self):
        await self.page.set_content("""
        <button class="collapsible-facet-wrapper__trigger" aria-expanded="false"
          onclick="if(!event.target.closest('.collapsible-facet-wrapper__trigger-label')) return;
          this.setAttribute('aria-expanded','true');document.querySelector('#live-editor').style.display='block'">
          <li-icon type="plus-icon" style="display:inline-block;width:20px;height:20px">+</li-icon>
          <div class="collapsible-facet-wrapper__trigger-label" data-test-toggle-label>Years of experience</div>
        </button>
        <div id="live-editor" style="display:none">
          <form class="range-slider-facet__form" onsubmit="event.preventDefault();window.updated=true">
            <label for="live-from">From</label><input name="range-from" id="live-from" type="number" value="0">
            <label for="live-to">to</label><input name="range-to" id="live-to" type="number" value="30">
            <input type="range" value="0"><input type="range" value="30">
            <button type="submit">Update</button>
          </form>
        </div><script>window.updated=false;</script>
        """)
        with contextlib.redirect_stdout(io.StringIO()):
            await search.apply_experience(self.page, "3-5 years")
        self.assertEqual(await self.page.locator("button.collapsible-facet-wrapper__trigger").get_attribute("aria-expanded"), "true")
        self.assertEqual(await self.page.locator("#live-from").input_value(), "3")
        self.assertEqual(await self.page.locator("#live-to").input_value(), "5")
        self.assertTrue(await self.page.evaluate("window.updated"))