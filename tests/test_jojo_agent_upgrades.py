import json
import unittest
from unittest.mock import patch

class WorkflowTests(unittest.TestCase):
    def test_relevant_guides_bounded(self):
        from jojo_playbooks import get_skill_guidance
        with patch('jojo_playbooks.active',return_value=True):
            result=get_skill_guidance('debug error browser research memory')
        self.assertEqual(len(result['skills']),2)

    def test_disabled_guidance_not_injected(self):
        from jojo_playbooks import context
        with patch('jojo_playbooks.active',return_value=False):
            self.assertEqual(context('debug error'),'')

    def test_individual_and_group_switch(self):
        from jojo_playbooks import active
        with patch('jojo_capabilities.allowed_tool',return_value=True), patch('jojo_playbooks.read_preferences',return_value={'capabilities':{'playbook:debugging':False}}):
            self.assertFalse(active('debugging'))
            self.assertTrue(active('research'))
        with patch('jojo_capabilities.allowed_tool',return_value=False):
            self.assertFalse(active('research'))

    def test_large_nested_output_bounded_and_marked(self):
        from jojo_tool_payload import bounded_payload
        result=bounded_payload({'rows':[{'text':'\\"\n'*10000}]*20,'error':'partial failure'})
        self.assertLessEqual(len(json.dumps(result,ensure_ascii=False)),12000)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['error'],'partial failure')
        self.assertIn('Narrow',result['notice'])

    def test_small_output_preserved_without_mutation(self):
        from jojo_tool_payload import bounded_payload
        original={'ok':False,'error':'missing'}
        result=bounded_payload(original)
        self.assertEqual(result,original)
        self.assertIsNot(result,original)

    def test_character_corrupt_settings_and_voice_unchanged(self):
        import jojo_character as character
        with patch.object(character,'read_preferences',return_value={'character':{'mode':[]}}):
            self.assertEqual(character.settings()['mode'],'companion')
        with patch.object(character,'save_preferences') as save:
            character.save('professional',followups=False)
            self.assertEqual(set(save.call_args.args[0]),{'character'})

    def test_pc_status_does_not_substitute_phone(self):
        from jojo_pc_status import command
        with patch('jojo_pc_status.snapshot') as snapshot:
            self.assertIsNone(command('pc status','mobile'))
            snapshot.assert_not_called()

    def test_pc_status_respects_permission(self):
        from jojo_pc_status import command
        with patch('jojo_capabilities.allowed_tool',return_value=False),patch('jojo_pc_status.snapshot') as snapshot:
            self.assertIn('disabled',command('pc status','laptop'))
            snapshot.assert_not_called()

    def test_dispatch_routes_pc_status_without_model(self):
        import jojo_core
        with patch('jojo_pc_status.snapshot',return_value={'cpu':12}), patch('jojo_capabilities.allowed_tool',return_value=True):
            self.assertIn('CPU 12%',jojo_core.dispatch_command('pc status','laptop'))

    def test_dispatch_character_and_old_learned_trigger(self):
        import jojo_core
        with patch('jojo_character.save_preferences') as save:
            self.assertIn('professional',jojo_core.dispatch_command('professional mode','laptop'))
            save.assert_called_once()
        with patch('jojo_workspace.private_session',return_value=False), patch.object(jojo_core,'get_learned_skills',return_value=[]):
            self.assertIsNone(jojo_core.check_learned_skill_trigger('unmatched request'))

    def test_pc_status_caveat(self):
        from jojo_pc_status import describe
        self.assertIn('ek sample',describe({'cpu':99,'battery':None}))

if __name__=='__main__':unittest.main()
