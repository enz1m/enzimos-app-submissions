"""New boundary: source-build admission must reject undeclared build authority."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('builder',Path(__file__).resolve().parents[1]/'tools/store_build.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class BuildPolicy(unittest.TestCase):
    def test_pinned_source_and_sandbox_inputs(self):
        manifest={'app-id':'org.example.App','runtime':'org.freedesktop.Platform','sdk':'org.freedesktop.Sdk','runtime-version':'25.08','command':'app','modules':[{'name':'app','buildsystem':'simple','build-commands':['make'],'sources':[{'type':'git','url':'https://github.com/example/app','commit':'a'*40,'disable-submodules':True}]}]}
        self.assertEqual(builder.inspect(manifest,'example/app','a'*40,'org.example.App')['sources'][0]['commit'],'a'*40)
        source=manifest['modules'][0]['sources'][0]
        for change in ({'commit':'b'*40},{'disable-submodules':False},{'url':'https://example.org/elsewhere'},{'branch':'main'}):
            original=source.copy();source.update(change)
            with self.assertRaises(ValueError):builder.inspect(manifest,'example/app','a'*40,'org.example.App')
            source.clear();source.update(original)
        manifest['build-options']={'build-args':['--share=network']}
        with self.assertRaises(ValueError):builder.inspect(manifest,'example/app','a'*40,'org.example.App')
        self.assertEqual(builder.configuration('{"ENZIM_API_ID":"example"}'),{'ENZIM_API_ID':'example'})
        with self.assertRaises(ValueError):builder.configuration('{"PATH":"/untrusted"}')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'manifest.json').write_text('{}');(root/'link.json').symlink_to(root/'manifest.json')
            self.assertEqual(builder.source_file(root,'manifest.json'),root/'manifest.json')
            for path in ('../manifest.json','link.json'):
                with self.assertRaises(ValueError):builder.source_file(root,path)


if __name__=='__main__':unittest.main()
