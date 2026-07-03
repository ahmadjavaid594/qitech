import importlib.util
import pathlib

root = pathlib.Path(r'c:/Users/ZuhairZikria/Documents/QiTechScripts')
spec = importlib.util.spec_from_file_location('run_all_migrations', root/'run_all_migrations.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
base_dir = root/'Migration Tables'
for p in mod.find_migration_scripts(base_dir):
    print(p.relative_to(root))
