"""Final policy contract, robustness, private history and identity invariance."""
import ast,copy,math,random,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from algorithm import StudentPolicy
from observation_fixture import observation

class FinalPolicyTests(unittest.TestCase):
    def make(self):
        p=StudentPolicy();p.reset({'delta_t_ms':200});return p
    def test_valid_actions_and_no_input_mutation(self):
        p=self.make();rng=random.Random(3014)
        for t in range(500):
            o=observation(10**rng.uniform(-2,1),10**rng.uniform(-2,1),t*200);before=copy.deepcopy(o)
            a=p.decide(o);self.assertIn(a['action'],['stay','request_handover']);self.assertEqual(o,before)
            if a['action']=='request_handover':self.assertIn(a['target_cell_id'],{c['cell_id'] for c in o['candidates']})
    def test_missing_and_nonfinite_measurements(self):
        for value in [None,float('nan'),float('inf'),'invalid']:
            o=observation();o['serving_rsrp_dbm']=value
            self.assertEqual(self.make().decide(o)['action'],'stay')
            o=observation();o['candidates'][0]['rs_sinr_db']=value
            self.assertIn(self.make().decide(o)['action'],['stay','request_handover'])
    def test_missing_optional_features(self):
        o=observation()
        for name in ['speed_mps','heading_deg','z_m']:o[name]=float('nan')
        self.assertIn(self.make().decide(o)['action'],['stay','request_handover'])
    def test_no_usable_candidates(self):
        for cs in [None,[],[{'cell_id':'target','eligible':False}]]:
            o=observation();o['candidates']=cs
            self.assertEqual(self.make().decide(o)['action'],'stay')
    def test_not_idle_or_not_attached(self):
        for phase in ['preparing','executing','rlf_recovery']:
            o=observation();o['ho_phase']=phase;self.assertEqual(self.make().decide(o)['action'],'stay')
        o=observation();o['serving_cell_id']=None;self.assertEqual(self.make().decide(o)['action'],'stay')
    def test_minimum_request_spacing(self):
        p=self.make();requests=[]
        for t in range(50):
            if p.decide(observation(time_ms=t*200))['action']=='request_handover':requests.append(t*200)
        self.assertGreater(len(requests),1)
        self.assertTrue(all(b-a>=1000 for a,b in zip(requests,requests[1:])))
    def test_bounded_private_history(self):
        p=self.make();other=self.make()
        for t in range(500):p.decide(observation(time_ms=t*200))
        self.assertTrue(all(len(h)<=20 for h in p.h.values()));self.assertEqual(other.h,{})
        p.reset({});self.assertEqual(p.h,{})
    def test_identifiers_and_absolute_position_not_model_inputs(self):
        a,b=self.make(),self.make()
        for t in range(30):
            x=observation(time_ms=t*200);y=copy.deepcopy(x)
            x.update(ue_id='one',x_m=0,y_m=0);y.update(ue_id='arbitrary',x_m=9999,y_m=-9999)
            self.assertEqual(a.decide(x),b.decide(y))
    def test_cell_renaming_preserves_decisions(self):
        a,b=self.make(),self.make();names={'serving':'alpha','target':'beta','other':'gamma'}
        for t in range(30):
            x=observation(time_ms=t*200);y=copy.deepcopy(x);y['serving_cell_id']=names[y['serving_cell_id']]
            for c in y['candidates']:c['cell_id']=names[c['cell_id']]
            aa=a.decide(x);bb=b.decide(y);self.assertEqual(aa['action'],bb['action'])
            if aa['action']=='request_handover':self.assertEqual(names[aa['target_cell_id']],bb['target_cell_id'])
    def test_model_structure_finite_and_immutable(self):
        p=self.make();self.assertIsInstance(p._trees,tuple)
        for tr in p._trees:
            self.assertIsInstance(tr,tuple)
            for f,cut,left,right,value in tr:
                self.assertTrue(math.isfinite(cut) and math.isfinite(value))
                if f>=0:
                    self.assertLess(f,39);self.assertTrue(0<=left<len(tr) and 0<=right<len(tr))
    def test_single_file_runtime_restrictions(self):
        path=ROOT/'algorithm.py';tree=ast.parse(path.read_text(encoding='utf-8'),feature_version=(3,11));imports=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):imports.extend(x.name for x in n.names)
            if isinstance(n,ast.ImportFrom):imports.append(n.module)
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):self.assertNotIn(n.func.id,{'open','eval','exec','__import__','compile'})
        self.assertTrue(set(imports)<={'math','statistics'});self.assertLessEqual(path.stat().st_size,1048576)

if __name__=='__main__':unittest.main(verbosity=2)
