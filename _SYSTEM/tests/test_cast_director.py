"""Multi-character source ownership, locked identity and credential recovery."""
import copy
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
from cast_contract import cast_profiles,validate_plan,should_route
from cast_pipeline import make_package,builder_source,cached_preview
from credential_store import load
from cast_review import review_batch,run as run_review
from deepseek_client import DeepSeekError


class CastDirectorTests(unittest.TestCase):
    def test_review_uses_native_pixels_and_rejects_modified_native_frame(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);row=root/'row.jpg'
            Image.new('RGB',(960,210),'blue').save(row)
            originals=[]
            for index in range(3):
                path=root/f'actual_{index}.png';Image.new('RGB',(640,360),'red').save(path);originals.append(path)
            request=dict(source=[{'id':1}],plan=dict(cast=[{'id':'king'}],scenes=[{'actors':['king']}]),
                images=[str(row)],image_hashes=[contract.sha(row)],actual_images=[list(map(str,originals))],
                actual_image_hashes=[list(map(contract.sha,originals))])
            contract.write_json(root/'request.json',request);client=Mock()
            client.generate.return_value=({'scenes':[{'cue_id':1,'status':'passed','issues':[]}]},{})
            with patch('cast_review.DeepSeekClient',return_value=client):run_review(root)
            with Image.open(root/'cue_001_review.jpg') as rendered:
                self.assertGreater(rendered.getpixel((300,400))[0],240)
                self.assertLess(rendered.getpixel((300,400))[2],10)
            (root/'batch_000.json').unlink();Image.new('RGB',(640,360),'green').save(originals[0])
            client.reset_mock()
            with patch('cast_review.DeepSeekClient',return_value=client),self.assertRaisesRegex(ValueError,'Actual frame changed'):
                run_review(root)
            client.generate.assert_not_called()

    def test_negative_image_findings_require_evidence_confirmation(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/'actual.jpg'
            Image.new('RGB',(960,210),'blue').save(path)
            request=dict(source=[{'id':1}],plan=dict(cast=[{'id':'king'}],scenes=[{'actors':['king']}]),
                images=[str(path)],image_hashes=[contract.sha(path)])
            contract.write_json(root/'request.json',request)
            failed={'scenes':[{'cue_id':1,'status':'repair_required','issues':['Right hand is clipped in the middle sample.']}]}
            client=Mock();client.generate.side_effect=[(failed,{'attempt':1}),(failed,{'attempt':2})]
            with patch('cast_review.DeepSeekClient',return_value=client):run_review(root)
            saved=contract.read_json(root/'batch_000.json')
            self.assertEqual(saved['initial_output'],failed);self.assertEqual(saved['output'],failed)
            self.assertEqual(contract.read_json(root/'review.json')['status'],'repair_required')
            images=[c for c in client.generate.call_args.args[0][-1]['content'] if c['type']=='image_url']
            self.assertEqual(len(images),3)
            self.assertTrue(all(i['image_url']['detail']=='original' for i in images))

    def test_throne_actions_reject_wrong_location_and_two_occupants(self):
        changed=copy.deepcopy(self.plan);scene=changed['scenes'][0]
        scene['beats'][0]['action']='rise'
        with self.assertRaisesRegex(ValueError,'requires the court throne'):validate_plan(changed,self.cues)
        scene['prop']='throne';scene['location']='room'
        with self.assertRaisesRegex(ValueError,'requires the court throne'):validate_plan(changed,self.cues)
        scene['location']='court';scene['beats'][1]['action']='sit'
        with self.assertRaisesRegex(ValueError,'one seated occupant'):validate_plan(changed,self.cues)

    def test_each_visual_request_binds_one_cue_to_one_actual_image(self):
        from PIL import Image
        import json
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);gallery=Image.new('RGB',(640,210),'red')
            gallery.paste(Image.new('RGB',(320,210),'green'),(320,0));gallery.save(root/'cast.png')
            images=[]
            for index,color in enumerate(('blue','yellow')):
                path=root/f'samples_{index}.png';Image.new('RGB',(960,210),color).save(path);images.append(path)
            request=dict(source=[{'id':1},{'id':2}],plan=dict(cast=[{'id':'king'},{'id':'boy'}],
                scenes=[{'actors':['king']},{'actors':['boy']}]),cast_image=str(root/'cast.png'),
                cast_image_sha256=contract.sha(root/'cast.png'),images=list(map(str,images)),image_hashes=list(map(contract.sha,images)))
            contract.write_json(root/'request.json',request);client=Mock()
            client.generate.side_effect=[({'scenes':[{'cue_id':i,'status':'passed','issues':[]}]},{'attempt':i}) for i in (1,2)]
            with patch('cast_review.DeepSeekClient',return_value=client):run_review(root)
            self.assertEqual(client.generate.call_count,2)
            for cue,call in enumerate(client.generate.call_args_list,1):
                content=call.args[0][1]['content']
                self.assertEqual(len([c for c in content if c['type']=='image_url']),1)
                self.assertEqual(json.loads(content[0]['text'])['source'],[{'id':cue}])
            with Image.open(root/'cue_001_review.jpg') as rendered:
                self.assertGreater(rendered.getpixel((150,100))[0],240)
                self.assertGreater(rendered.getpixel((400,300))[2],240)
            with Image.open(root/'cue_002_review.jpg') as rendered:
                self.assertGreater(rendered.getpixel((150,100))[1],110)
                self.assertGreater(rendered.getpixel((400,300))[0],240)

    def test_empty_visual_api_content_retries_once_without_claiming_usage(self):
        client=Mock();client.generate.side_effect=[DeepSeekError('DeepSeek returned no final JSON content.'),
            ({'scenes':[{'cue_id':1,'status':'passed','issues':[]}]},{'attempt':2})]
        output,evidence=review_batch(client,[],{},[{'id':1}])
        self.assertEqual(output['scenes'][0]['status'],'passed')
        self.assertEqual(client.generate.call_count,2);self.assertIsNone(evidence[0]['usage'])

    def test_authentication_failure_is_not_retried(self):
        client=Mock();client.generate.side_effect=DeepSeekError('DeepSeek HTTP 401: Key rejected.')
        with self.assertRaises(DeepSeekError):review_batch(client,[],{},[{'id':1}])
        self.assertEqual(client.generate.call_count,1)

    def test_visual_contract_repair_keeps_blocking_image_findings(self):
        client=Mock()
        client.generate.side_effect=[
            ({'scenes':[{'cue_id':1,'status':'passed','issues':['Coins hidden behind lid.']}]},{'attempt':1}),
            ({'scenes':[{'cue_id':1,'status':'repair_required','issues':['Coins hidden behind lid.']}]},{'attempt':2})]
        output,evidence=review_batch(client,[],{},[{'id':1}])
        self.assertEqual(output['scenes'][0]['status'],'repair_required')
        self.assertEqual(len(evidence),2)
        self.assertIn('do not change a failing verdict',client.generate.call_args.args[0][-1]['content'])

    def test_invalid_visual_response_stops_after_one_contract_repair(self):
        client=Mock();client.generate.return_value=({'scenes':[{'cue_id':2,'status':'passed','issues':[]}]},{})
        with self.assertRaisesRegex(ValueError,'source order'):
            review_batch(client,[],{},[{'id':1}])
        self.assertEqual(client.generate.call_count,2)

    def setUp(self):
        self.cues=[dict(id=1,start=0,end=1040,text='The king offers coins to the boy.'),
            dict(id=2,start=1040,end=2080,text='The boy chooses silver and the king laughs.')]
        self.cast=[dict(id='king',role='king',age='mature',evidence='king',face_style='angular',hair_style='side_part',costume='royal'),
            dict(id='boy',role='boy',age='child',evidence='boy',face_style='round',hair_style='textured_crop',costume='casual')]
        base=dict(location='court',actors=['king','boy'],speaker='king',listener='boy',prop='coins',camera='two_shot',emotion='warm',
            intent='The giver offers two different coins to the waiting child.')
        self.scenes=[dict(base,cue_id=1,evidence='offers coins',beats=[dict(actor='king',action='offer_coins'),dict(actor='boy',action='think'),dict(actor='boy',action='ask')]),
            dict(base,cue_id=2,evidence='chooses silver',beats=[dict(actor='boy',action='choose_silver'),dict(actor='king',action='laugh'),dict(actor='boy',action='smile')])]
        self.plan=dict(cast=self.cast,scenes=self.scenes)

    def test_locked_cast_changes_proportions_and_costume(self):
        first=cast_profiles(self.plan,self.cues);self.assertEqual(first,cast_profiles(self.plan,self.cues))
        self.assertNotEqual(first[0]['profile']['identity_id'],first[1]['profile']['identity_id'])
        self.assertLess(first[1]['scale'],first[0]['scale'])
        self.assertNotEqual(first[0]['profile']['appearance']['shape'],first[1]['profile']['appearance']['shape'])

    def test_api_child_hairstyle_is_not_replaced_by_host_default(self):
        plan=copy.deepcopy(self.plan);plan['cast'][1]['hair_style']='soft_curls'
        self.assertEqual(cast_profiles(plan,self.cues)[1]['profile']['appearance']['hairstyle'],'soft_curls')

    def test_shared_costume_class_still_has_distinct_locked_garments(self):
        plan=copy.deepcopy(self.plan)
        for actor in plan['cast']:actor['costume']='formal';actor['age']='adult'
        profiles=cast_profiles(plan,self.cues)
        self.assertNotEqual(profiles[0]['profile']['appearance']['palette']['shirt'],profiles[1]['profile']['appearance']['palette']['shirt'])

    def test_unsupported_actor_props_and_source_order_rejected(self):
        for field,value in [('actors',['invented']),('prop','none'),('cue_id',9),('evidence','invented evidence')]:
            changed=copy.deepcopy(self.plan);changed['scenes'][0][field]=value
            with self.assertRaises(Exception):validate_plan(changed,self.cues)

    def test_secondary_explicit_role_cannot_be_omitted(self):
        cues=copy.deepcopy(self.cues);cues[1]['text']+=' The nobles accuse him.'
        with self.assertRaisesRegex(ValueError,'omits explicitly'):validate_plan(self.plan,cues)

    def test_camera_only_variation_cannot_hide_repeated_staging(self):
        changed=copy.deepcopy(self.plan);changed['scenes'][1]=dict(changed['scenes'][0],cue_id=2,evidence='king',camera='wide')
        with self.assertRaisesRegex(ValueError,'Repeated'):validate_plan(changed,self.cues)

    def test_continuing_conversation_cannot_flip_screen_positions(self):
        changed=copy.deepcopy(self.plan);changed['scenes'][1]['actors']=['boy','king']
        with self.assertRaisesRegex(ValueError,'flipped left-to-right'):validate_plan(changed,self.cues)

    def test_one_scene_per_line_preserves_frame_rounding_overlap(self):
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/'reports') as temp:
            root=Path(temp);source=root/'input.srt'
            source.write_text('1\n00:00:00,000 --> 00:00:01,040\n'+self.cues[0]['text']+'\n\n2\n00:00:01,040 --> 00:00:02,080\n'+self.cues[1]['text']+'\n')
            package,project,_=make_package(root,source,self.cues,self.plan,cast_profiles(self.plan,self.cues))
            self.assertEqual(len(project['scenes']),2);self.assertEqual(project['total_frames'],50)
            self.assertEqual([s['params']['semantic_cues'] for s in project['scenes']],[[1],[2]])
            self.assertEqual(project['scenes'][0]['source_cues'],[1,2])
            self.assertEqual(contract.sha(source),contract.sha(package/'source.srt'))

    def test_coin_ownership_continues_until_a_new_offer(self):
        cues=copy.deepcopy(self.cues)
        for i,text in ((3,'The king laughs while the boy smiles.'),(4,'The king offers coins again.')):
            cues.append(dict(id=i,start=(i-1)*1040,end=i*1040,text=text))
        scenes=copy.deepcopy(self.scenes)
        scenes.append(dict(scenes[-1],cue_id=3,evidence='boy smiles',beats=[dict(actor='king',action='laugh'),dict(actor='boy',action='smile'),dict(actor='boy',action='wait')]))
        scenes.append(dict(scenes[0],cue_id=4,evidence='offers coins',beats=[dict(actor='king',action='offer_coins'),dict(actor='boy',action='wait'),dict(actor='king',action='smile')]))
        plan=dict(cast=self.cast,scenes=scenes)
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/'reports') as temp:
            root=Path(temp);source=root/'source.srt'
            def stamp(ms):
                return f'00:00:{ms//1000:02},{ms%1000:03}'
            source.write_text('\n\n'.join(str(c['id'])+'\n'+stamp(c['start'])+' --> '+stamp(c['end'])+'\n'+c['text'] for c in cues)+'\n')
            _,project,_=make_package(root,source,cues,plan,cast_profiles(plan,cues))
            self.assertEqual(project['scenes'][2]['params']['initial_coin_owner'],'boy')
            self.assertNotIn('initial_coin_owner',project['scenes'][3]['params'])

    def test_source_with_two_supported_roles_selects_cast_route(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);contract.write_json(root/'_SYSTEM/multi_cast.json',dict(enabled=True,mode='auto'))
            self.assertTrue(should_route(root,self.cues))
            self.assertFalse(should_route(root,[dict(text='A person works alone.')]))

    def test_tampered_preview_cannot_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);names=['geometry_qa.json','build_report.json']+[f'preview_{i:02}.png' for i in (1,2,3)]
            for name in names:(root/name).write_bytes(b'original')
            contract.write_json(root/'preview_integrity.json',{name:contract.sha(root/name) for name in names})
            self.assertTrue(cached_preview(root));(root/'preview_02.png').write_bytes(b'tampered')
            self.assertFalse(cached_preview(root))

    def test_encrypted_backup_recovers_empty_and_missing_text_without_logging_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'secrets';root.mkdir();path=root/'deepseek_api_key.txt';path.write_text('test-only-credential')
            self.assertEqual(load(path),'test-only-credential');backup=path.with_suffix('.dpapi')
            self.assertNotIn(b'test-only-credential',backup.read_bytes())
            path.write_text('');self.assertEqual(load(path),'test-only-credential')
            path.unlink();self.assertEqual(load(path),'test-only-credential')
            self.assertNotIn('test-only-credential',(root/'credential_status.json').read_text())

    def test_local_reset_never_selects_credentials(self):
        import motion
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for folder in ('INPUT','OUTPUT','_SYSTEM/work','_SYSTEM/secrets'):(root/folder).mkdir(parents=True)
            (root/'_SYSTEM/secrets/deepseek_api_key.txt').write_text('test credential')
            self.assertEqual(motion.reset_plan(root),[])

    def test_registered_builder_passes_source_policy(self):
        contract.blender_code(builder_source())


if __name__=='__main__':unittest.main()
