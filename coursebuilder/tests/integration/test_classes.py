# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Functional tests for Course Builder."""

__author__ = [
    'John Orr (jorr@google.com)'
]

import collections
import os
import random
import subprocess
import time
import urllib
import urllib2
import zipfile

import pageobjects
from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.chrome import options
from selenium.webdriver.support import expected_conditions as ec

from models import models
from models import transforms
from modules.embed import embed
from tests import suite
from tests.integration import fake_visualizations

BROWSER_WIDTH = 1600
BROWSER_HEIGHT = 1000


class BaseIntegrationTest(suite.TestBase):
    """Base class for all integration tests."""

    LOGIN = 'test@example.com'

    def setUp(self):
        super(BaseIntegrationTest, self).setUp()
        chrome_options = options.Options()
        chrome_options.add_argument('--disable-extensions')

        # Sadly, the max wait for the driver to become ready is hard-coded at
        # 30 seconds.  However, that seems like it'd be enough for our
        # purposes, so retrying the whole shebang seems like a better bet for
        # getting rid of the flakiness due to occasional failure to connect to
        # the Chrome driver.
        self.driver = None
        tries = 10
        while not self.driver:
            tries -= 1
            try:
                self.driver = webdriver.Chrome(chrome_options=chrome_options)
            except exceptions.WebDriverException, ex:
                print ex
                if tries:
                    print 'Retrying Chrome connection up to %d more times' % (
                        tries)
                else:
                    raise ex

        # Set a large enough window size independent of screen size so that all
        # click actions can be performed correctly.
        self.driver.set_window_size(BROWSER_WIDTH, BROWSER_HEIGHT)

    def tearDown(self):
        time.sleep(1)  # avoid broken sockets on the server
        self.driver.quit()
        super(BaseIntegrationTest, self).tearDown()

    def load_root_page(self):
        ret = pageobjects.RootPage(self).load(
            suite.TestBase.INTEGRATION_SERVER_BASE_URL)
        tries = 10
        while tries and 'This webpage is not avail' in self.driver.page_source:
            tries -= 1
            time.sleep(1)
            ret = pageobjects.RootPage(self).load(
                suite.TestBase.INTEGRATION_SERVER_BASE_URL)
        return ret

    def load_dashboard(self, name):
        return pageobjects.DashboardPage(self).load(
            suite.TestBase.INTEGRATION_SERVER_BASE_URL, name)

    def load_appengine_admin(self, course_name):
        return pageobjects.AppengineAdminPage(
            self, suite.TestBase.ADMIN_SERVER_BASE_URL, course_name)

    def load_sample_course(self):
        # Be careful using this method. Multiple clicks against the 'explore
        # sample course' button create multiple courses with different slugs, in
        # different namespaces. Because integration tests are not well isolated,
        # this can lead to a number of subtle collisions between tests that do
        # not manifest when the tests are run individually, but *do* manifest
        # when run en bloc. Prefer create_new_course() whenever possible.
        return self.load_root_page(
        ).load_welcome_page(
            self.INTEGRATION_SERVER_BASE_URL
        ).click_explore_sample_course()

    def get_slug_for_current_course(self):
        """Returns the slug for the current course based on the current URL."""
        return '/' + self.driver.current_url.split('/')[3]

    def get_uid(self):
        """Generate a unique id string."""
        uid = ''
        for i in range(10):  # pylint: disable=unused-variable
            j = random.randint(0, 61)
            if j < 26:
                uid += chr(65 + j)  # ascii capital letters
            elif j < 52:
                uid += chr(97 + j - 26)  # ascii lower case letters
            else:
                uid += chr(48 + j - 52)  # ascii digits
        return uid

    def create_new_course(self, login=True):
        """Create a new course with a unique name, using the admin tools."""
        uid = self.get_uid()
        name = 'ns_%s' % uid
        title = 'Test Course (%s)' % uid

        page = self.load_root_page()

        if login:
            page.click_login(
            ).login(
                self.LOGIN, admin=True
            )

        page.click_dashboard(
        ).click_admin(
        ).click_add_course(
        ).set_fields(
            name=name, title=title, email='a@bb.com'
        ).click_save(
            link_text='Add New Course', status_message='Added.', post_wait=True
        )

        return (name, title)

    def set_admin_setting(self, setting_name, state):
        """Configure a property on Admin setting page."""

        self.load_root_page(
        ).click_dashboard(
        ).click_admin(
        ).click_site_settings(
        ).click_override(
            setting_name
        ).set_value(
            state
        ).set_status(
            'Active'
        ).click_save(
        ).click_close()


class EmbedModuleTest(BaseIntegrationTest):

    # Ideally we'd fetch this programmatically, but the integration tests can't
    # see app contexts, and we don't want to refactor the DOM to make it
    # accessible.
    SAMPLE_COURSE_TITLE = 'Power Searching with Google'

    def setUp(self):
        super(EmbedModuleTest, self).setUp()
        self.email = 'test@example.com'

    def assert_embed_has_error(self, page, error):
        self.assertIsNotNone(page)
        self.assertTrue(page.has_error(error))

    def assert_is_embed_page(self, page, embedded_course_title):
        self.assertIsNotNone(page)
        page_text = page.get_text()
        self.assertIn('Greetings, %s.' % self.email, page_text)
        self.assertIn(embedded_course_title, page_text)

    def assert_is_sign_in_page(self, page):
        self.assertIsNotNone(page)
        self.assertIn('start', page.get_text().lower())

    def get_demo_child_url(self, name):
        return (
            suite.TestBase.INTEGRATION_SERVER_BASE_URL + embed._DEMO_CHILD_URL +
            '?slug=' + name)

    def get_demo_url(self):
        return (
            suite.TestBase.INTEGRATION_SERVER_BASE_URL + embed._DEMO_URL)

    def get_global_errors_url(self):
        return (
            suite.TestBase.INTEGRATION_SERVER_BASE_URL +
            embed._GLOBAL_ERRORS_DEMO_URL)

    def get_local_errors_url(self):
        return (
            suite.TestBase.INTEGRATION_SERVER_BASE_URL +
            embed._LOCAL_ERRORS_DEMO_URL)

    def make_course_enrollable(self, name):
        self.load_dashboard(
            name
        ).click_lock(
        ).click_registration(
        ).set_whitelisted_students(
            [self.email]
        )

    def set_child_courses_and_make_course_available(
            self, parent_name, child_name):
        self.load_dashboard(
            parent_name
        ).click_lock(
        ).click_advanced_settings(
        ).click_advanced_edit(
        ).set_child_courses(
            [child_name]
        )

    def test_embed_global_errors(self):
        self.load_sample_course()
        pageobjects.RootPage(self).load(
            suite.TestBase.INTEGRATION_SERVER_BASE_URL).click_logout()

        global_error_page = pageobjects.EmbedModuleDemoPage(self).load(
            self.get_global_errors_url())

        # Because both widgets have configuration errors, the embeds are both in
        # state error and no sign-in widget is shown.
        cb_embeds = global_error_page.get_cb_embed_elements()

        self.assertEquals(2, len(cb_embeds))

        first_error_page = global_error_page.load_embed(
            cb_embeds[0], wait_for=pageobjects.EmbedModuleStateError)
        global_error_message = (
            'Embed src '
            '"http://other:8081/sample/modules/embed/v1/resource/example/1" '
            'does not match origin "http://localhost:8081"')

        self.assert_embed_has_error(first_error_page, global_error_message)

        second_error_page = global_error_page.load_embed(
            cb_embeds[1], wait_for=pageobjects.EmbedModuleStateError)
        global_error_message = (
            'Embed src '
            '"http://localhost:8082/sample/modules/embed/v1/resource/example/'
            '2" does not match origin "http://localhost:8081"')
        local_error_message = (
            'Embed src '
            '"http://localhost:8082/sample/modules/embed/v1/resource/example/'
            '2" does not match first cb-embed src found, which is from the '
            'deployment at "http://other:8081/sample/modules/embed/v1". '
            'All cb-embeds in a single page must be from the same Course '
            'Builder deployment.')

        self.assert_embed_has_error(second_error_page, global_error_message)
        self.assert_embed_has_error(second_error_page, local_error_message)

    def test_embed_local_errors(self):
        self.load_sample_course()
        pageobjects.RootPage(self).load(
            suite.TestBase.INTEGRATION_SERVER_BASE_URL).click_logout()

        local_error_page = pageobjects.EmbedModuleDemoPage(self).load(
            self.get_local_errors_url())

        # Before signing in, the first embed shows the sign-in widget, and the
        # second shows both a global and a local error.
        cb_embeds = local_error_page.get_cb_embed_elements()

        self.assertEquals(2, len(cb_embeds))
        self.assert_is_sign_in_page(
            local_error_page.load_embed(
                cb_embeds[0], wait_for=pageobjects.EmbedModuleStateSignIn))

        second_embed_page = local_error_page.load_embed(
            cb_embeds[1], wait_for=pageobjects.EmbedModuleStateError)
        global_error_message = (
            'Embed src '
            '"http://localhost:8082/sample/modules/embed/v1/resource/example/'
            '2" does not match origin "http://localhost:8081"')
        local_error_message = (
            'Embed src '
            '"http://localhost:8082/sample/modules/embed/v1/resource/example/'
            '2" does not match first cb-embed src found, which is from the '
            'deployment at "http://localhost:8081/sample/modules/embed/v1". '
            'All cb-embeds in a single page must be from the same Course '
            'Builder deployment.')

        self.assert_embed_has_error(second_embed_page, global_error_message)
        self.assert_embed_has_error(second_embed_page, local_error_message)

        # After signing in, the first embed shows content and the second embed
        # shows both a global and a local error.
        local_error_page.login(self.email)

        cb_embeds = local_error_page.get_cb_embed_elements()

        self.assertEquals(2, len(cb_embeds))

        first_embed_page = local_error_page.load_embed(cb_embeds[0])
        second_embed_page = local_error_page.load_embed(
            cb_embeds[1], wait_for=pageobjects.EmbedModuleStateError)

        self.assert_is_embed_page(first_embed_page, self.SAMPLE_COURSE_TITLE)
        self.assert_embed_has_error(second_embed_page, global_error_message)
        self.assert_embed_has_error(second_embed_page, local_error_message)

    def test_embed_render_lifecycle_for_child_course(self):
        child_name, child_title = self.create_new_course()
        self.make_course_enrollable(child_name)
        parent_name = self.create_new_course(login=False)[0]
        self.set_child_courses_and_make_course_available(
            parent_name, child_name)
        pageobjects.RootPage(self).load(
            suite.TestBase.INTEGRATION_SERVER_BASE_URL).click_logout()
        demo_page = pageobjects.EmbedModuleDemoPage(self).load(
            self.get_demo_child_url(parent_name))
        embeds = demo_page.get_cb_embed_elements()

        self.assertTrue(len(embeds) == 1)

        for cb_embed in embeds:
            page = demo_page.load_embed(
                cb_embed, wait_for=pageobjects.EmbedModuleStateSignIn)
            self.assert_is_sign_in_page(page)

        demo_page.login(self.email)

        # Force refetch of embeds because login state changed.
        for cb_embed in demo_page.get_cb_embed_elements():
            page = demo_page.load_embed(cb_embed)
            self.assert_is_embed_page(page, child_title)

    def test_embed_render_lifecycle_for_single_course(self):
        dashboard_page = self.load_sample_course()
        pageobjects.RootPage(self).load(
            suite.TestBase.INTEGRATION_SERVER_BASE_URL).click_logout()
        demo_page = pageobjects.EmbedModuleDemoPage(self).load(
            self.get_demo_url())
        embeds = demo_page.get_cb_embed_elements()

        self.assertTrue(len(embeds) == 3)

        for cb_embed in embeds:
            page = demo_page.load_embed(
                cb_embed, wait_for=pageobjects.EmbedModuleStateSignIn)
            self.assert_is_sign_in_page(page)

        demo_page.login(self.email)

        # Force refetch of embeds because login state changed.
        for cb_embed in demo_page.get_cb_embed_elements():
            page = demo_page.load_embed(cb_embed)
            self.assert_is_embed_page(page, self.SAMPLE_COURSE_TITLE)


class IntegrationServerInitializationTask(BaseIntegrationTest):

    def test_setup_default_course(self):
        self.load_root_page()._add_default_course_if_needed(
            suite.TestBase.INTEGRATION_SERVER_BASE_URL)


class EtlTranslationRoundTripTest(BaseIntegrationTest):

    def setUp(self):
        super(EtlTranslationRoundTripTest, self).setUp()
        self.archive_path = self._get_archive_path('translations.zip')

    def _delete_archive_file(self):
        os.remove(self.archive_path)

    def _get_archive_path(self, name):
        return os.path.join(self.test_tempdir, name)

    def _get_etl_sh_abspath(self):
        cb_home = os.environ.get('COURSEBUILDER_HOME')
        if not cb_home:
            raise Exception('Could not find COURSEBUILDER_HOME')

        return os.path.join(cb_home, 'scripts/etl.sh')

    def _get_ln_locale_element(self, page, pre_wait=True):
        try:
            return page.find_element_by_css_selector(
                'thead > tr > th:nth-child(3)', pre_wait=pre_wait)
        except exceptions.NoSuchElementException:
            return None

    # For these _run* methods: Integration tests are not well isolated. When
    # multiple tests click the button to create a sample course, they may end up
    # with different slugs. The slug is used to create the ETL command lines, so
    # we must always parse the slug out of the driver's URL so the ETL commands
    # target the correct namespace.
    def _run_download_course(self):
        etl_command = [
            'download', 'course', self.get_slug_for_current_course(),
            'mycourse', 'localhost:8081', '--archive_path', self.archive_path]
        self._run_etl_command(etl_command)

    def _run_download_datastore(self):
        etl_command = [
            'download', 'datastore', self.get_slug_for_current_course(),
            'mycourse', 'localhost:8081', '--archive_path', self.archive_path]
        self._run_etl_command(etl_command)

    def _run_delete_job(self):
        etl_command = [
            'run', 'modules.i18n_dashboard.jobs.DeleteTranslations',
            self.get_slug_for_current_course(), 'mycourse', 'localhost:8081']
        self._run_etl_command(etl_command)

    def _run_download_job(self):
        etl_command = [
            'run', 'modules.i18n_dashboard.jobs.DownloadTranslations',
            self.get_slug_for_current_course(), 'mycourse', 'localhost:8081',
            '--job_args=' + self.archive_path]
        self._run_etl_command(etl_command)

    def _run_translate_job(self):
        etl_command = [
            'run', 'modules.i18n_dashboard.jobs.TranslateToReversedCase',
            self.get_slug_for_current_course(), 'mycourse', 'localhost:8081']
        self._run_etl_command(etl_command)

    def _run_upload_job(self):
        etl_command = [
            'run', 'modules.i18n_dashboard.jobs.UploadTranslations',
            self.get_slug_for_current_course(), 'mycourse', 'localhost:8081',
            '--job_args=' + self.archive_path]
        self._run_etl_command(etl_command)

    def _run_etl_command(self, etl_command):
        etl_command = (['sh', self._get_etl_sh_abspath()] + etl_command)
        process = subprocess.Popen(
            etl_command, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
            stdout=subprocess.PIPE)
        process.stdin.write('anything@example.com\nany_password\n')
        process.stdin.flush()
        _, stderr = process.communicate()

        if process.returncode:
            raise Exception(
                'Unable to run etl command "%s", stderr was %s' % (
                    ' '.join(etl_command), stderr))

    def assert_archive_file_exists(self):
        self.assertTrue(os.path.exists(self.archive_path))

    def assert_ln_locale_in_course(self, page):
        self.assertTrue(self._get_ln_locale_element(page))

    def assert_ln_locale_not_in_course(self, page):
        self.assertFalse(self._get_ln_locale_element(page, pre_wait=False))

    def assert_zipfile_contains_only_ln_locale(self):
        self.assert_archive_file_exists()

        with zipfile.ZipFile(self.archive_path) as zf:
            files = zf.infolist()
            self.assertEqual(
                ['locale/ln/LC_MESSAGES/messages.po'],
                [f.filename for f in files])

    def test_full_round_trip_of_data_via_i18n_dashboard_module_jobs(self):
        page = self.load_sample_course().click_i18n()
        self.assert_ln_locale_not_in_course(page)

        self._run_translate_job()
        page.click_i18n()
        self.assert_ln_locale_in_course(page)

        self._run_download_job()
        self.assert_zipfile_contains_only_ln_locale()

        ln_locale = self._get_ln_locale_element(page)
        self._run_delete_job()
        page.click_i18n()
        page.wait().until(ec.staleness_of((ln_locale)))
        self.assert_ln_locale_not_in_course(page)

        self._run_upload_job()
        page.click_i18n()
        self.assert_ln_locale_in_course(page)

        # As an additional sanity check, make sure we can download the course
        # definitions and datastore data for a course with translations.

        self._delete_archive_file()
        self._run_download_course()
        self.assert_archive_file_exists()

        self._delete_archive_file()
        self._run_download_datastore()
        self.assert_archive_file_exists()


class SampleCourseTests(BaseIntegrationTest):
    """Integration tests on the sample course installed with Course Builder."""

    def test_admin_can_add_announcement(self):
        uid = self.get_uid()
        login = 'test-%s@example.com' % uid
        title = 'Test announcement (%s)' % uid

        self.load_root_page(
        ).click_login(
        ).login(login, admin=True)

        self.load_root_page(
        ).click_announcements(
        ).click_add_new(
        ).enter_fields(
            title=title,
            date='2013-03-01',
            body='The new announcement'
        ).click_save(
        ).click_close(
        ).verify_announcement(
            title=title + ' (Draft)', date='2013-03-01',
            body='The new announcement')

    def test_admin_can_change_admin_user_emails(self):
        uid = self.get_uid()
        login = 'test-%s@example.com' % uid
        email = 'new-admin-%s@foo.com' % uid

        self.load_root_page(
        ).click_login(
        ).login(
            login, admin=True
        ).click_dashboard(
        ).click_admin(
        ).click_site_settings(
        ).click_override_admin_user_emails(
        ).set_value(
            email
        ).set_status(
            'Active'
        ).click_save(
        ).click_close(
        ).verify_admin_user_emails_contains(email)


class AdminTests(BaseIntegrationTest):
    """Tests for the administrator interface."""

    LOGIN = 'test@example.com'

    def test_default_course_is_read_only(self):
        self.load_root_page(
        ).click_login(
        ).login(
            self.LOGIN, admin=True
        ).click_dashboard(
        ).verify_read_only_course()

    def test_create_new_course(self):
        self.create_new_course()

    def test_add_unit(self):
        name = self.create_new_course()[0]

        self.load_dashboard(
            name
        ).verify_not_publicly_available(
        ).click_add_unit(
        ).set_title(
            'Test Unit 1'
        ).set_status(
            'Public'
        ).click_save(
        ).click_close(
        ).verify_course_outline_contains_unit('Unit 1 - Test Unit 1')

    def test_rte_codemirror(self):
        """Test that CodeMirror is working properly with rte."""

        name = self.create_new_course()[0]

        unit_title = 'Test Unit 1'
        unit_header_html = '<h1> header </h1> <p> paragraph </p>'

        self.load_dashboard(
            name
        ).click_add_unit(
        ).set_title(
            unit_title
        ).set_status(
            'Public'
        ).click_plain_text(
        ).setvalue_codemirror(
            0, unit_header_html
        ).assert_equal_codemirror(
            0, unit_header_html
        ).click_save(
        ).click_close(
        ).click_edit_unit(
            'Unit 1 - ' + unit_title
        ).assert_equal_codemirror(
        # recheck that the data is really on the server
            0, unit_header_html
        ).click_close()

    def test_in_place_lesson_editing(self):
        name = self.create_new_course()[0]
        self.load_dashboard(
            name
        ).click_add_unit(
        ).set_title(
            'Test Unit 1'
        ).set_status(
            'Public'
        ).click_save(
        ).click_close(
        ).verify_course_outline_contains_unit(
            'Unit 1 - Test Unit 1'
        ).click_add_lesson(
        ).set_title(
            'Test Lesson'
        ).select_settings(
        ).set_status(
            'Public'
        ).select_content(
        ).click_plain_text(
        ).setvalue_codemirror(
            0, 'Lorem ipsum'
        ).click_save(
        ).click_close(
        ).click_on_course_outline_components(
            '1. Test Lesson'
        ).click_edit_lesson(
        ).edit_lesson_iframe_assert_equal_codemirror(
            'Lorem ipsum'
        ).edit_lesson_iframe_setvalue_codemirror(
            'Lorem ipsum dolor sit amet'
        ).edit_lesson_iframe_click_save(
        ).assert_lesson_content_contains('Lorem ipsum dolor sit amet')

    def test_cancel_add_with_no_changes_should_not_need_confirm(self):
        """Test entering editors and clicking close without making changes."""

        name = self.create_new_course()[0]

        # Test Import
        self.load_dashboard(name).click_import(
        ).click_close(
        ).verify_not_publicly_available()  # confirm that we're on the dashboard

        # Test Add Link
        self.load_dashboard(name).click_add_link(
        ).click_close(
        ).verify_not_publicly_available()  # confirm that we're on the dashboard

        # Test Add Unit
        self.load_dashboard(name).click_add_unit(
        ).click_close(
        ).verify_not_publicly_available()  # confirm that we're on the dashboard

        # Test Add Lesson
        self.load_dashboard(name).click_add_lesson(
        ).click_close(
        ).verify_not_publicly_available()  # confirm that we're on the dashboard

        # Test Upload asset
        self.load_dashboard(name).click_edit(
        ).click_sub_tab(
            'Images'
        ).click_upload(
        ).click_close(
        ).verify_selected_group('edit')

    def test_leave_page_with_changes_triggers_alert(self):
        """Opens an editor page, make changes and tries to leave.

        Expects an alert for confirmation.
        """
        name = self.create_new_course()[0]
        confirm_message = ('You have unsaved changes that will be lost if'
                           ' you leave.')
        # Test back arrow
        browser = self.load_dashboard(name).click_add_unit(
        ).set_contents_on_one_page(True).go_back()
        alert = browser.switch_to_alert()
        self.assertEqual(confirm_message, alert.text)
        alert.accept()
        self.assertEqual(browser.where_am_i(), 'dashboard')

        # Test click close button
        browser = self.load_dashboard(name).click_add_unit(
        ).set_contents_on_one_page(True).click_close()
        alert = browser.switch_to_alert()
        self.assertEqual(confirm_message, alert.text)
        alert.accept()
        self.assertEqual(browser.where_am_i(), 'dashboard')

        # Test click navigation bar button
        dashboard = self.load_dashboard(name)
        dashboard.click_add_unit().set_contents_on_one_page(True)
        dashboard.click_edit()
        alert = browser.switch_to_alert()
        self.assertEqual(confirm_message, alert.text)
        alert.accept()
        self.assertEqual(browser.where_am_i(), 'dashboard?action=outline')

        # Test cancel the alert
        browser = self.load_dashboard(name).click_add_unit(
        ).set_contents_on_one_page(True).go_back()
        browser.switch_to_alert().dismiss()
        self.assertNotEqual(browser.where_am_i(), 'dashboard')

    def test_upload_and_delete_image(self):
        """Admin should be able to upload an image and then delete it."""
        image_file = os.path.join(
            os.path.dirname(__file__), 'assets', 'img', 'test.png')

        name = self.create_new_course()[0]

        self.load_dashboard(
            name
        ).click_edit(
        ).click_sub_tab(
            'Images'
        ).click_upload(
        ).select_file(
            image_file
        ).click_upload_and_expect_saved(
        ).verify_image_file_by_name(
            'assets/img/test.png'
        ).click_edit_image(
            'assets/img/test.png'
        ).click_delete(
        ).confirm_delete(
        ).verify_no_image_file_by_name('assets/img/test.png')

    def test_add_and_edit_custom_tags(self):
        name = self.create_new_course()[0]
        instanceid_regex = 'instanceid="[A-Za-z0-9]{12}"'

        self.load_dashboard(
            name
        ).click_add_unit(
        ).set_title(
            'First Unit'
        ).click_save(
        ).click_close(
        ).click_add_lesson(
        ).click_rich_text(
        ).send_rte_text(
            'YouTube:'
        ).click_rte_add_custom_tag(
            'YouTube Video'
        ).set_rte_lightbox_field(
            'input[name=videoid]', '123'
        ).click_rte_save(
        ).click_preview(
        ).ensure_preview_document_matches_regex(
            'YouTube:<div class="gcb-video-container">'
        ).click_plain_text(
        ).ensure_instanceid_count_equals(
            1
        ).take_snapshot_of_instanceid_list(
        ).click_rich_text(
        ).doubleclick_rte_element(
            'img.gcbMarker'
        ).ensure_rte_lightbox_field_has_value(
            'input[name=videoid]', '123'
        ).set_rte_lightbox_field(
            'input[name=videoid]', '321'
        ).click_rte_save(
        ).click_plain_text(
        ).ensure_lesson_body_textarea_matches_regex(
            'YouTube:<gcb-youtube videoid="321" %s>'
            '</gcb-youtube>' % instanceid_regex
        ).ensure_instanceid_list_matches_last_snapshot(
        ).click_rich_text(
        ).send_rte_text(
            'Google Group:'
        ).click_rte_add_custom_tag(
            'Google Group'
        ).set_rte_lightbox_field(
            'input[name=group]', 'abc'
        ).set_rte_lightbox_field(
            'input[name=category]', 'def'
        ).click_rte_save(
        ).click_plain_text(
        ).ensure_lesson_body_textarea_matches_regex(
            'YouTube:<gcb-youtube videoid="321" %s></gcb-youtube>'
            'Google Group:'
            '<gcb-googlegroup group="abc" category="def" %s>'
            '</gcb-googlegroup>' % (instanceid_regex, instanceid_regex)
        ).click_save(
        #---------- Test editor state is saved ----------
        ).click_close(
        ).click_edit_lesson(
            0
        ).assert_editor_mode_is_html(
        ).click_rich_text(
        ).click_save(
        ).click_close(
        ).click_edit_lesson(
            0
        ).assert_editor_mode_is_rich_text()

    def test_add_edit_delete_label(self):
        name = self.create_new_course()[0]

        self.load_dashboard(
            name
        ).click_edit(
        ).click_sub_tab(
            'Labels'
        ).click_add_label(
        ).set_title(
            'Liver'
        ).set_description(
            'Exercise and diet to support healthy hepatic function'
        ).set_type(
            models.LabelDTO.LABEL_TYPE_COURSE_TRACK
        ).click_save(
        ).click_close(
        ).verify_label_present(
            'Liver'
        ).click_edit_label(
            'Liver'
        ).verify_title(
            'Liver'
        ).verify_description(
            'Exercise and diet to support healthy hepatic function'
        ).verify_type(
            models.LabelDTO.LABEL_TYPE_COURSE_TRACK
        ).set_title(
            'Kidney'
        ).click_save(
        ).click_close(
        ).verify_label_present(
            'Kidney'
        ).click_edit_label(
            'Kidney'
        ).click_delete(
        ).confirm_delete(
        ).verify_label_not_present(
            'Kidney'
        ).verify_label_not_present(
            'Liver'
        )


class QuestionsTest(BaseIntegrationTest):

    def test_inline_question_creation(self):
        name = self.create_new_course()[0]

        self.load_dashboard(
            name
        ).click_add_unit(
        ).set_title(
            'Test Unit'
        ).click_save(
        ).click_close(
        ).click_add_lesson(
        ).set_title(
            'Test Lesson'
        ).click_rich_text(

        #---------------------------------------------- Add a MC question
        ).click_rte_add_custom_tag(
            'Question'
        ).click_rte_element(
            '#mc_tab'
        ).set_rte_lightbox_field(
            '.mc-container [name="description"]', 'mc question'
        ).set_rte_lightbox_field(
            '.question-weight [name="weight"]', '23'
        ).set_rte_lightbox_field(
            '.mc-container .yui-editor-editable', 'What color is the sky?',
            index=0, clear=False
        ).set_rte_lightbox_field(
            '.mc-container .yui-editor-editable', 'Blue',
            index=2, clear=False
        ).click_rte_link(
            'Add a choice'
        ).set_rte_lightbox_field(
            '.mc-container .yui-editor-editable', 'Red',
            index=4, clear=False
        ).click_rte_link(
            'Add a choice'
        ).set_rte_lightbox_field(
            '.mc-container .yui-editor-editable', 'Green',
            index=6, clear=False
        ).click_rte_link(
            'Add a choice'
        ).set_rte_lightbox_field(
            '.mc-container .yui-editor-editable', 'Yellow',
            index=8, clear=False
        ).click_rte_save(
        ).doubleclick_rte_element(
            'img'
        ).ensure_rte_lightbox_field_has_value(
            '.mc-container [name="description"]', 'mc question'
        ).ensure_rte_lightbox_field_has_value(
            '.question-weight [name="weight"]', '23'
        ).click_rte_close(
        ).click_preview(
        #---------------------------------------------- Confirm in preview
        ).ensure_preview_document_matches_regex(
            '23 points'
        ).ensure_preview_document_matches_regex(
            'What color is the sky?'
        ).click_rich_text(

        #---------------------------------------------- Add a SA questions
        ).click_rte_add_custom_tag(
            'Question'
        ).click_rte_element(
            '#sa_tab'
        ).set_rte_lightbox_field(
            '.sa-container [name="description"]', 'sa question',
        ).set_rte_lightbox_field(
            '.question-weight [name="weight"]', '24',
        ).set_rte_lightbox_field(
            '.sa-container .yui-editor-editable', 'Type "woof"',
            index=0, clear=False
        ).set_rte_lightbox_field(
            '.sa-container [name="graders[0]response"]', 'woof'
        ).click_rte_save(
        ).doubleclick_rte_element(
            'img:nth-of-type(2)', index=0
        ).ensure_rte_lightbox_field_has_value(
            '.sa-container [name="description"]', 'sa question'
        ).ensure_rte_lightbox_field_has_value(
            '.question-weight [name="weight"]', '24'
        ).click_rte_close(
        ).click_preview(
        #---------------------------------------------- Confirm in preview
        ).ensure_preview_document_matches_regex(
            '24 points'
        ).ensure_preview_document_matches_regex(
            'Type "woof"'
        ).ensure_preview_document_matches_regex(
            '23 points'
        ).ensure_preview_document_matches_regex(
            'What color is the sky?'
        )

    def test_add_question_and_solve_it(self):
        name = self.create_new_course()[0]

        # Note the occasional breaks in the fluent structure of the code in this
        # test are because Pylint has stack overflow problems with very long
        # chained expressions

        page = self.load_dashboard(
            name
        ).click_course(
        ).click_register(
        ).enroll(
            'John Smith'
        ).click_course(
        ).click_dashboard(

        #---------------------------------------------- Question
        ).click_edit(
        ).click_sub_tab(
            'Questions'
        ).click_add_multiple_choice(
        ).set_question(
            'What is your favorite color?'
        ).set_description(
            'Multiple choice question'
        ).set_answer(
            0, 'Red'
        ).click_add_choice(
        ).set_answer(
            1, 'Blue'
        ).click_add_choice(
        ).set_answer(
            2, 'Yellow'
        ).click_add_choice(
        ).set_answer(
            3, 'Pink'
        ).click_save(
        ).click_close(
        ).verify_question_exists(
            'Multiple choice question'
        ).click_question_preview(
        ).verify_question_preview(
            'What is your favorite color?'
        ).click_outline(
        ).verify_not_publicly_available(
        #---------------------------------------------- Unit
        ).click_add_unit(
        ).set_title(
            'Test Unit 1'
        ).set_status(
            'Public'
        ).set_contents_on_one_page(
            True
        ).click_save(
        ).click_close(
        ).verify_course_outline_contains_unit(
            'Unit 1 - Test Unit 1'
        #---------------------------------------------- Lesson 1 (graded)
        ).click_add_lesson(
        ).set_title(
            'Question lesson - Graded'
        ).select_settings(
        ).set_status(
            'Public'
        ).set_questions_are_scored(
        ).select_content(
        ).click_rich_text(
        ).click_rte_add_custom_tag(
            'Question'
        ).set_rte_lightbox_field(
            '.question-weight input[name=weight]', 1
        ).click_rte_element(
            '.select-container [name="quid"] option:nth-child(2)'
        ).click_rte_save(
        ).click_save(
        ).click_close(
        #---------------------------------------------- Lesson 2 (ungraded)
        ).click_add_lesson(
        ).set_title(
            'Question lesson - UnGraded'
        ).select_settings(
        ).set_status(
            'Public'
        ).select_content(
        ).click_rich_text(
        ).click_rte_add_custom_tag(
            'Question'
        ).set_rte_lightbox_field(
            '.question-weight input[name=weight]', 1
        ).click_rte_element(
            '.select-container [name="quid"] option:nth-child(2)'
        ).click_rte_save(
        ).click_save(
        ).click_close(
        #---------------------------------------------- Assessment pre (ID 4)
        )

        page = page.click_add_assessment(
        ).set_title(
            'Pre-Assessment'
        ).set_status(
            'Public'
        ).click_rich_text(
            pageobjects.AddAssessment.INDEX_CONTENT
        ).click_rte_add_custom_tag(
            'Question',
            pageobjects.AddAssessment.INDEX_CONTENT
        ).set_rte_lightbox_field(
            '.question-weight input[name=weight]', 1
        ).click_rte_element(
            '.select-container [name="quid"] option:nth-child(2)'
        ).click_rte_save(
        ).click_save(
        ).click_close(
        #---------------------------------------------- Assessment post (ID 5)
        ).click_add_assessment(
        ).set_title(
            'Post-Assessment'
        ).set_status(
            'Public'
        ).click_rich_text(
            pageobjects.AddAssessment.INDEX_CONTENT
        ).click_rte_add_custom_tag(
            'Question',
            pageobjects.AddAssessment.INDEX_CONTENT
        ).set_rte_lightbox_field(
            '.question-weight input[name=weight]', 1
        ).click_rte_element(
            '.select-container [name="quid"] option:nth-child(2)'
        ).click_rte_save(
        ).click_save(
        ).click_close(
        #---------------------------------------------- Add assessments to unit
        ).click_edit_unit(
            'Unit 1 - Test Unit 1'
        ).set_pre_assessment(
            'Pre-Assessment'
        ).set_post_assessment(
            'Post-Assessment'
        ).click_save(
        ).click_close(
        ).click_on_course_outline_components(
            '2. Question lesson - UnGraded'
        #---------------------------------------------- Verify pre-assessment
        )

        page.set_answer_for_mc_question(
            'A4', 'What is your favorite color?', 'Red'
        ).submit_question_batch(
            'A4', 'Submit Answers'
        ).verify_correct_submission(
        ).return_to_unit(
        #---------------------------------------------- Verify non-graded
        ).set_answer_for_mc_question(
            'L3', 'What is your favorite color?', 'Yellow'
        ).submit_question_batch(
            'L3', 'Check Answer'
        ).verify_incorrect_submission(
            'L3', 'What is your favorite color?'
        ).set_answer_for_mc_question(
            'L3', 'What is your favorite color?', 'Red'
        ).submit_question_batch(
            'L3', 'Check Answer'
        ).verify_correct_submission(
            'L3', 'What is your favorite color?'
        #---------------------------------------------- Verify graded
        ).set_answer_for_mc_question(
            'L2', 'What is your favorite color?', 'Red'
        ).submit_question_batch(
            'L2', 'Grade Questions'
        ).verify_correct_grading(
            'L2'
        ).set_answer_for_mc_question(
            'L2', 'What is your favorite color?', 'Pink'
        ).submit_question_batch(
            'L2', 'Grade Questions'
        ).verify_incorrect_grading(
            'L2'
        #---------------------------------------------- Verify post-assessment
        ).set_answer_for_mc_question(
            'A5', 'What is your favorite color?', 'Blue'
        ).submit_question_batch(
            'A5', 'Submit Answers'
        ).verify_incorrect_submission(
        ).return_to_unit()


class VisualizationsTest(BaseIntegrationTest):

    def setUp(self):
        super(VisualizationsTest, self).setUp()
        self._name = self.create_new_course()[0]

    def _have_page_number(self, page, data_source, page_number):
        return (page.get_data_page_number(data_source) == page_number and
                page.get_displayed_page_number(data_source) == str(page_number))

    def _assert_have_page_number(self, page, data_source, page_number):
        self.assertEquals(page_number, page.get_data_page_number(data_source))
        self.assertEquals(str(page_number), page.get_displayed_page_number(
            data_source))

    def _wait_for_page_number(self, page, data_source, page_number):
        max_time = time.time() + 10
        while (time.time() < max_time and
               not self._have_page_number(page, data_source, page_number)):
            time.sleep(0.1)
        self._assert_have_page_number(page, data_source, page_number)

    def _force_response_common(self, data_source, action, page_number=0):
        url = (suite.TestBase.INTEGRATION_SERVER_BASE_URL +
               fake_visualizations.ForceResponseHandler.URL)
        fp = urllib2.urlopen(url, urllib.urlencode({
            fake_visualizations.ForceResponseHandler.PARAM_DATA_SOURCE:
                data_source,
            fake_visualizations.ForceResponseHandler.PARAM_ACTION:
                action,
            fake_visualizations.ForceResponseHandler.PARAM_PAGE_NUMBER:
                page_number,
            }))
        fp.read()
        fp.close()

    def _force_response_exception(self, data_source):
        self._force_response_common(
            data_source,
            fake_visualizations.ForceResponseHandler.ACTION_EXCEPTION)

    def _force_response_log_critical(self, data_source):
        self._force_response_common(
            data_source,
            fake_visualizations.ForceResponseHandler.ACTION_LOG_CRITICAL)

    def _force_response_page_number(self, data_source, page_number):
        self._force_response_common(
            data_source,
            fake_visualizations.ForceResponseHandler.ACTION_PAGE_NUMBER,
            page_number)

    def test_exams_simple(self):
        page = self.load_dashboard(self._name).click_analytics('Exams')

        # Seeing this zero proves we have really loaded data to page via REST.
        self.assertEquals(0, page.get_data_page_number('exams'))

        # Verify that page controls and page number are not displayed.
        self.assertEquals('', page.get_displayed_page_number(
            'exams', pre_wait=False))
        self.assertFalse(page.buttons_present('exams', pre_wait=False))

        self._force_response_log_critical('exams')
        page = self.load_dashboard(self._name).click_analytics(
            'Exams').wait_until_logs_not_empty('exams')
        page.wait_until_logs_not_empty('exams')
        self.assertEquals('critical: Error for testing',
                          page.get_data_source_logs('exams'))

        self._force_response_exception('exams')
        page = self.load_dashboard(self._name).click_analytics(
            'Exams').wait_until_logs_not_empty('exams')

        page.wait_until_logs_not_empty('exams')
        self.assertRegexpMatches(
            page.get_data_source_logs('exams'),
            'critical: Fetching results data: ValueError: Error for testing')

    def test_pupils_page_navigation(self):
        page = self.load_dashboard(self._name).click_analytics('Pupils')

        # Initial load of page shoud use data page zero
        self._assert_have_page_number(page, 'pupils', 0)

        # Click forward to data page 1
        page.click('pupils', 'plusone')
        self._wait_for_page_number(page, 'pupils', 1)

        # Pretend that page 1 is the last with data; click forward.
        self._force_response_page_number('pupils', 1)
        page.click('pupils', 'plusone')
        self._wait_for_page_number(page, 'pupils', 1)
        page.wait_until_logs_not_empty('pupils')
        self.assertEquals('warning: Stopping at last page 1',
                          page.get_data_source_logs('pupils'))
        page.click('pupils', 'minusone')
        self._wait_for_page_number(page, 'pupils', 0)

        page.click('pupils', 'plusten')
        self._wait_for_page_number(page, 'pupils', 10)
        page.click('pupils', 'plusone')
        self._wait_for_page_number(page, 'pupils', 11)
        page.click('pupils', 'plusten')
        self._wait_for_page_number(page, 'pupils', 21)
        page.click('pupils', 'plusone')
        self._wait_for_page_number(page, 'pupils', 22)

        self._force_response_page_number('pupils', 22)
        page.click('pupils', 'plusten')
        self._wait_for_page_number(page, 'pupils', 22)
        page.wait_until_logs_not_empty('pupils')
        self.assertEquals('warning: Stopping at last page 22',
                          page.get_data_source_logs('pupils'))

        page.click('pupils', 'minusone')
        self._wait_for_page_number(page, 'pupils', 21)
        page.click('pupils', 'minusone')
        self._wait_for_page_number(page, 'pupils', 20)
        page.click('pupils', 'minusone')
        self._wait_for_page_number(page, 'pupils', 19)
        page.click('pupils', 'minusten')
        self._wait_for_page_number(page, 'pupils', 9)
        page.click('pupils', 'minusten')
        self._wait_for_page_number(page, 'pupils', 0)
        page.click('pupils', 'minusone')
        self._wait_for_page_number(page, 'pupils', 0)
        page.click('pupils', 'minusten')
        self._wait_for_page_number(page, 'pupils', 0)

    def test_pupils_caching(self):
        page = self.load_dashboard(self._name).click_analytics('Pupils')
        self._assert_have_page_number(page, 'pupils', 0)
        page.click('pupils', 'plusone')
        self._wait_for_page_number(page, 'pupils', 1)
        page.click('pupils', 'plusone')
        self._wait_for_page_number(page, 'pupils', 2)

        # Pretend page one now has a problem on the server side;
        # click back to page one.  We expect to _not_ see that
        # exception, since we've cached page one.
        self._force_response_log_critical('pupils')
        page.click('pupils', 'minusone')
        self._wait_for_page_number(page, 'pupils', 1)
        self.assertEquals('', page.get_page_level_logs())

        # Now change the number of items in a data page; click back
        # to page zero.  We _do_ expect to now see that exception,
        # since we should drop our cached pages since the parameters
        # to the page selection have changed.
        page.set_chunk_size('pupils', 3)
        page.click('pupils', 'minusone')
        self._wait_for_page_number(page, 'pupils', 0)
        page.wait_until_logs_not_empty('pupils')
        self.assertEquals('critical: Error for testing',
                          page.get_data_source_logs('pupils'))

    def test_dimension_gc(self):
        page = self.load_dashboard(self._name).click_analytics('Scoring')
        self._wait_for_page_number(page, 'fake_answers', 0)

        # Scoring page has a pie chart.
        self.assertTrue(page.answers_pie_chart_present())

        # If we haven't been cleaning up crossfilter dimensions, when
        # we hit 32, crossfilter will pitch a fit and the chart won't
        # display.
        for _ in range(32):
            page.click('fake_answers', 'minusone')
        self.assertTrue(page.answers_pie_chart_present())

    def test_data_sources_independent(self):
        page = self.load_dashboard(self._name).click_analytics('Scoring')
        self._wait_for_page_number(page, 'pupils', 0)
        self._wait_for_page_number(page, 'fake_answers', 0)

        self._force_response_log_critical('fake_answers')
        self._force_response_exception('pupils')

        page.click('pupils', 'plusone')
        self._wait_for_page_number(page, 'pupils', 0)
        self._wait_for_page_number(page, 'fake_answers', 0)
        page.wait_until_logs_not_empty('pupils')
        self.assertRegexpMatches(
            page.get_data_source_logs('pupils'),
            'critical: Fetching results data: ValueError: Error for testing')
        self.assertEquals('', page.get_data_source_logs('fake_answers'))

        page.click('pupils', 'plusone')
        self._wait_for_page_number(page, 'pupils', 1)
        self._wait_for_page_number(page, 'fake_answers', 0)
        self.assertEquals('', page.get_data_source_logs('pupils'))
        self.assertEquals('', page.get_data_source_logs('fake_answers'))

        page.click('fake_answers', 'plusone')
        self._wait_for_page_number(page, 'pupils', 1)
        self._wait_for_page_number(page, 'fake_answers', 1)
        self.assertEquals('', page.get_data_source_logs('pupils'))
        page.wait_until_logs_not_empty('fake_answers')
        self.assertEquals('critical: Error for testing',
                          page.get_data_source_logs('fake_answers'))


class EventsTest(BaseIntegrationTest):

    def test_html5_video_events(self):
        name = self.create_new_course()[0]

        # Set gcb_can_persist_tag_events so we will track video events.

        thing = self.load_root_page(
        ).click_dashboard(
        ).click_admin(
        ).click_site_settings(
        ).click_override(
            'gcb_can_persist_tag_events'
        ).set_value(
            True
        ).set_status(
            'Active'
        ).click_save()

        # Add a unit with a video.
        instanceid_list = []
        self.load_dashboard(
            name
        ).click_add_unit(
        ).set_title(
            'First Unit'
        ).set_status(
            'Public'
        ).click_rich_text(
            pageobjects.AddUnit.INDEX_UNIT_HEADER
        ).click_rte_add_custom_tag(
            'HTML5 Video'
        ).set_rte_lightbox_field(
            'input[name=url]',
            'http://techslides.com/demos/sample-videos/small.mp4'
        ).click_rte_save(
        ).click_plain_text(
        ).take_snapshot_of_instanceid_list(
            instanceid_list
        ).click_save(
        )
        instanceid = instanceid_list[0]

        # Load the unit with the video and fiddle with the controls.
        self.load_dashboard(
            name
        ).click_on_course_outline_components(
            'Unit 1 - First Unit'
        ).wait_for_video_state(
            instanceid, 'readyState', 4, 10
        ).play_video(
            instanceid
        ).wait_for_video_state(
            instanceid, 'paused', None, 10
        ).pause_video(
            instanceid
        ).wait_for_video_state(
            instanceid, 'paused', True, 10
        ).play_video(
            instanceid
        ).wait_for_video_state(
            instanceid, 'ended', True, 10
        )

        # Verify that we have two events logged: load-start, and error.
        data = self.load_appengine_admin(
            name
        ).get_datastore(
            'EventEntity'
        ).get_items(
        )

        events = []
        for datum in data:
            events.append(transforms.loads(datum['data']))
        events.sort(key=lambda event: event['event_id'])

        # Sometimes get this, sometimes don't.  Don't check for this to
        # avoid flakiness.
        if events[0]['event_type'] == 'loadstart':
            del events[0]

        ExpectedEvent = collections.namedtuple(
            'ExpectedEvent', ['event_type', 'position'])
        expected_events = [
            ExpectedEvent('loadeddata', 'zero'),
            ExpectedEvent('play', 'zero'),
            ExpectedEvent('playing', 'zero'),
            ExpectedEvent('pause', 'middle'),
            ExpectedEvent('play', 'middle'),
            ExpectedEvent('playing', 'middle'),
            ExpectedEvent('pause', 'end'),
            ExpectedEvent('ended', 'end'),
            ]

        end_position = 5.568
        for event, expected in zip(events, expected_events):
            self.assertEquals(instanceid, event['instance_id'])
            self.assertEquals(1, event['rate'])
            self.assertEquals(1, event['default_rate'])
            self.assertEquals(expected.event_type, event['event_type'])
            if expected.position == 'zero':
                self.assertEquals(0, event['position'])
            elif expected.position == 'middle':
                self.assertNotEquals(0, event['position'])
                self.assertNotEquals(end_position, event['position'])
            elif expected.position == 'end':
                self.assertEquals(end_position, event['position'])


class IntegrationTestBundle1(
        AdminTests, EventsTest, EtlTranslationRoundTripTest, QuestionsTest,
        SampleCourseTests):
    """Test bundle that forces serial execution of all containing tests."""
    pass
