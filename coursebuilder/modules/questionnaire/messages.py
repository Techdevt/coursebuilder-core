# Copyright 2015 Google Inc. All Rights Reserved.
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

"""Messages used in the questionnaire module."""

__author__ = [
    'johncox@google.com (John Cox)',
]

from common import safe_dom


# TODO(johncox): replace placeholder URL once target link is determined.
RTE_QUESTIONNAIRE_DISABLE_FIELDS = safe_dom.assemble_text_message("""
If checked, the form will display with all fields disabled. This is used to
display the results of a questionnaire on a different page.
""", 'https://code.google.com/p/course-builder/wiki/Dashboard')

# TODO(johncox): replace placeholder URL once target link is determined.
RTE_QUESTIONNAIRE_FORM_ID = safe_dom.assemble_text_message("""
This is the unique ID for this form.
""", 'https://code.google.com/p/course-builder/wiki/Dashboard')

RTE_QUESTIONNAIRE_SUBMISSION_TEXT = """
This text is displayed to the student after they submit their responses.
"""

RTE_QUESTIONNAIRE_SUBMIT_LABEL = """
This text is displayed on the submit button.
"""
