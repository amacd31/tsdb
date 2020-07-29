import gc
import os
import shutil
import tempfile
import unittest

from phildb.database import PhilDB
from phildb.create import create
from phildb.exceptions import AlreadyExistsError


class CreateDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        # On Windows files can't be removed while still open.
        # The time between the db object going out of scope and tear down
        # occurring is too short for garbage collection to have run.
        # As a result SQLAlchemy has not released the sqlite file by the
        # time tear down occurs.
        # This results in an error on Windows:
        #     PermissionError: [WinError 32] The process cannot access the file
        #     because it is being used by another process:
        # Therefore garbage collect before trying to remove temporary files.
        gc.collect()
        try:
            shutil.rmtree(self.temp_dir)
        except OSError as e:
            if e.errno != 2:  # Code 2: No such file or directory.
                raise

    def test_create_new(self):
        db_name = os.path.join(self.temp_dir, "new_project")
        create(db_name)
        db = PhilDB(db_name)
        self.assertEqual(os.path.exists(db._PhilDB__meta_data_db()), True)

    def test_create_existing_dir(self):
        db_name = os.path.join(self.temp_dir)
        create(db_name)
        db = PhilDB(db_name)
        self.assertEqual(os.path.exists(db._PhilDB__meta_data_db()), True)

    def test_protect_existing(self):
        db_name = os.path.join(self.test_data_dir, "test_tsdb")
        with self.assertRaises(AlreadyExistsError) as context:
            create(db_name)

        self.assertEqual(
            str(context.exception),
            "PhilDB database already exists at: {0}".format(db_name),
        )
