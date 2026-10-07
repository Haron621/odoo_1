from odoo.fields import Command
from odoo.http import request

from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment


class WebsiteHrRecruitmentSkills(WebsiteHrRecruitment):

    # A real application form is a handful of checkboxes. Anything past this is
    # a crafted request, and every entry costs an hr.applicant.skill insert.
    _max_submitted_skills = 50

    def extract_data(self, model_sudo, values):
        if model_sudo.model != 'hr.applicant':
            return super().extract_data(model_sudo, values)

        values = dict(values)
        # The skill type checkboxes are disabled, so they are not submitted by
        # the form; drop them anyway rather than trust the request.
        values.pop('applicant_skill_ids', None)
        # dict.fromkeys drops duplicates while keeping the submitted order. Two
        # rows for one skill violate the "one active skill per skill_id" rule in
        # hr.individual.skill.mixin, and that would take the application down.
        skill_ids = list(dict.fromkeys(
            int(s) for s in values.pop('skill_ids', '').split(',') if s.strip().isdigit()
        ))[:self._max_submitted_skills]

        data = super().extract_data(model_sudo, values)
        if skill_ids:
            data['record']['applicant_skill_ids'] = [
                Command.create({
                    'skill_id': skill.id,
                    'skill_type_id': skill.skill_type_id.id,
                    'skill_level_id': self._get_default_skill_level(skill).id,
                })
                for skill in request.env['hr.skill'].sudo().browse(skill_ids).exists()
            ]
        return data

    def _get_default_skill_level(self, skill):
        # `skill_level_id` is required, so give it the value the backend form
        # would: the level flagged as `default_level`, or the first one of the
        # skill type.
        levels = skill.skill_type_id.skill_level_ids
        return levels.filtered('default_level')[:1] or levels[:1]
