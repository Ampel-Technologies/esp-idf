#!/usr/bin/env python
#
# SPDX-FileCopyrightText: 2019-2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import json
import os
import shutil
import subprocess
import sys
from typing import Any
from typing import List
from unittest import main
from unittest import mock
from unittest import TestCase

import jsonschema

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

try:
    import idf
except ImportError:
    sys.path.append('..')
    import idf

current_dir = os.path.dirname(os.path.realpath(__file__))
idf_py_path = os.path.join(current_dir, '..', 'idf.py')
extension_path = os.path.join(current_dir, 'test_idf_extensions', 'test_ext')
py_actions_path = os.path.join(current_dir, '..', 'idf_py_actions')
link_path = os.path.join(py_actions_path, 'test_ext')


class TestWithoutExtensions(TestCase):
    @classmethod
    def setUpClass(cls):
        # Disable the component manager and extra extensions for these tests
        cls.env_patcher = mock.patch.dict(os.environ, {
            'IDF_COMPONENT_MANAGER': '0',
            'IDF_EXTRA_ACTIONS_PATH': '',
        })
        cls.env_patcher.start()

        super().setUpClass()


class TestExtensions(TestWithoutExtensions):
    def test_extension_loading(self):
        try:
            os.symlink(extension_path, link_path)
            os.environ['IDF_EXTRA_ACTIONS_PATH'] = os.path.join(current_dir, 'extra_path')
            output = subprocess.check_output([sys.executable, idf_py_path, '--help'],
                                             env=os.environ).decode('utf-8', 'ignore')

            self.assertIn('--test-extension-option', output)
            self.assertIn('test_subcommand', output)
            self.assertIn('--some-extension-option', output)
            self.assertIn('extra_subcommand', output)
        finally:
            os.remove(link_path)

    def test_extension_execution(self):
        try:
            os.symlink(extension_path, link_path)
            os.environ['IDF_EXTRA_ACTIONS_PATH'] = ';'.join([os.path.join(current_dir, 'extra_path')])
            output = subprocess.check_output(
                [sys.executable, idf_py_path, '--some-extension-option=awesome', 'test_subcommand', 'extra_subcommand'],
                env=os.environ).decode('utf-8', 'ignore')
            self.assertIn('!!! From some global callback: awesome', output)
            self.assertIn('!!! From some subcommand', output)
            self.assertIn('!!! From test global callback: test', output)
            self.assertIn('!!! From some subcommand', output)
        finally:
            os.remove(link_path)

    def test_hidden_commands(self):
        try:
            os.symlink(extension_path, link_path)
            os.environ['IDF_EXTRA_ACTIONS_PATH'] = ';'.join([os.path.join(current_dir, 'extra_path')])
            output = subprocess.check_output([sys.executable, idf_py_path, '--help'],
                                             env=os.environ).decode('utf-8', 'ignore')
            self.assertIn('test_subcommand', output)
            self.assertNotIn('hidden_one', output)

        finally:
            os.remove(link_path)


class TestDependencyManagement(TestWithoutExtensions):
    def test_dependencies(self):
        result = idf.init_cli()(
            args=['--dry-run', 'flash'],
            standalone_mode=False,
        )
        self.assertEqual(['flash'], list(result.keys()))

    def test_order_only_dependencies(self):
        result = idf.init_cli()(
            args=['--dry-run', 'build', 'fullclean', 'all'],
            standalone_mode=False,
        )
        self.assertEqual(['fullclean', 'all'], list(result.keys()))

    def test_repeated_dependencies(self):
        result = idf.init_cli()(
            args=['--dry-run', 'fullclean', 'app', 'fullclean', 'fullclean'],
            standalone_mode=False,
        )
        self.assertEqual(['fullclean', 'app'], list(result.keys()))

    def test_complex_case(self):
        result = idf.init_cli()(
            args=['--dry-run', 'clean', 'monitor', 'clean', 'fullclean', 'flash'],
            standalone_mode=False,
        )
        self.assertEqual(['fullclean', 'clean', 'flash', 'monitor'], list(result.keys()))

    def test_dupplicated_commands_warning(self):
        capturedOutput = StringIO()
        sys.stderr = capturedOutput
        idf.init_cli()(
            args=['--dry-run', 'clean', 'monitor', 'build', 'clean', 'fullclean', 'all'],
            standalone_mode=False,
        )
        sys.stderr = sys.__stderr__
        self.assertIn(
            'WARNING: Commands "all", "clean" are found in the list of commands more than once.',
            capturedOutput.getvalue())

        sys.stderr = capturedOutput
        idf.init_cli()(
            args=['--dry-run', 'clean', 'clean'],
            standalone_mode=False,
        )
        sys.stderr = sys.__stderr__
        self.assertIn(
            'WARNING: Command "clean" is found in the list of commands more than once.', capturedOutput.getvalue())


class TestVerboseFlag(TestWithoutExtensions):
    def test_verbose_messages(self):
        output = subprocess.check_output(
            [
                sys.executable,
                idf_py_path,
                '-C%s' % current_dir,
                '-v',
                'test-verbose',
            ], env=os.environ).decode('utf-8', 'ignore')

        self.assertIn('Verbose mode on', output)

    def test_verbose_messages_not_shown_by_default(self):
        output = subprocess.check_output(
            [
                sys.executable,
                idf_py_path,
                '-C%s' % current_dir,
                'test-verbose',
            ], env=os.environ).decode('utf-8', 'ignore')

        self.assertIn('Output from test-verbose', output)
        self.assertNotIn('Verbose mode on', output)


class TestGlobalAndSubcommandParameters(TestWithoutExtensions):
    def test_set_twice_same_value(self):
        """Can set -D twice: globally and for subcommand if values are the same"""

        idf.init_cli()(
            args=['--dry-run', '-DAAA=BBB', '-DCCC=EEE', 'build', '-DAAA=BBB', '-DCCC=EEE'],
            standalone_mode=False,
        )

    def test_set_twice_different_values(self):
        """Cannot set -D twice: for command and subcommand of idf.py (with different values)"""

        with self.assertRaises(idf.FatalError):
            idf.init_cli()(
                args=['--dry-run', '-DAAA=BBB', 'build', '-DAAA=EEE', '-DCCC=EEE'],
                standalone_mode=False,
            )


class TestDeprecations(TestWithoutExtensions):
    def test_exit_with_error_for_subcommand(self):
        try:
            subprocess.check_output(
                [sys.executable, idf_py_path, '-C%s' % current_dir, 'test-2'], env=os.environ, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            self.assertIn('Error: Command "test-2" is deprecated and was removed.', e.output.decode('utf-8', 'ignore'))

    def test_exit_with_error_for_option(self):
        try:
            subprocess.check_output(
                [sys.executable, idf_py_path, '-C%s' % current_dir, '--test-5=asdf'],
                env=os.environ,
                stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            self.assertIn(
                'Error: Option "test_5" is deprecated since v2.0 and was removed in v3.0.',
                e.output.decode('utf-8', 'ignore'))

    def test_deprecation_messages(self):
        output = subprocess.check_output(
            [
                sys.executable,
                idf_py_path,
                '-C%s' % current_dir,
                '--test-0=a',
                '--test-1=b',
                '--test-2=c',
                '--test-3=d',
                'test-0',
                '--test-sub-0=sa',
                '--test-sub-1=sb',
                'ta',
                'test-1',
            ],
            env=os.environ,
            stderr=subprocess.STDOUT).decode('utf-8', 'ignore')

        self.assertIn('Warning: Option "test_sub_1" is deprecated and will be removed in future versions.', output)
        self.assertIn(
            'Warning: Command "test-1" is deprecated and will be removed in future versions. '
            'Please use alternative command.', output)
        self.assertIn('Warning: Option "test_1" is deprecated and will be removed in future versions.', output)
        self.assertIn(
            'Warning: Option "test_2" is deprecated and will be removed in future versions. '
            'Please update your parameters.', output)
        self.assertIn('Warning: Option "test_3" is deprecated and will be removed in future versions.', output)
        self.assertNotIn('"test-0" is deprecated', output)
        self.assertNotIn('"test_0" is deprecated', output)


class TestHelpOutput(TestWithoutExtensions):
    def action_test_idf_py(self, commands: List[str], schema: Any) -> None:
        env = dict(**os.environ)
        python = shutil.which('python', path=env['PATH'])
        if python is None:
            raise ValueError('python not found')
        idf_path = env.get('IDF_PATH')
        if idf_path is None:
            raise ValueError('Empty IDF_PATH')
        idf_py_cmd = [
            python,
            os.path.join(idf_path, 'tools', 'idf.py')
        ]
        commands = idf_py_cmd + commands
        output_file = 'idf_py_help_output.json'
        with open(output_file, 'w') as outfile:
            subprocess.run(commands, env=env, stdout=outfile)
        with open(output_file, 'r') as outfile:
            help_obj = json.load(outfile)
        self.assertIsNone(jsonschema.validate(help_obj, schema))

    def test_output(self):
        with open(os.path.join(current_dir, 'idf_py_help_schema.json'), 'r') as schema_file:
            schema_json = json.load(schema_file)
        self.action_test_idf_py(['help', '--json'], schema_json)
        self.action_test_idf_py(['help', '--json', '--add-options'], schema_json)


class TestFileArgumentExpansion(TestCase):
    def test_file_expansion(self):
        """Test @filename expansion functionality"""
        try:
            output = subprocess.check_output(
                [sys.executable, idf_py_path, '--version', '@file_args_expansion_inputs/args_a'],
                env=os.environ,
                stderr=subprocess.STDOUT).decode('utf-8', 'ignore')
            self.assertIn('Running: idf.py --version DAAA DBBB', output)
        except subprocess.CalledProcessError as e:
            self.fail(f'Process should have exited normally, but it exited with a return code of {e.returncode}')

    def test_multiple_file_arguments(self):
        """Test multiple @filename arguments"""
        try:
            output = subprocess.check_output(
                [sys.executable, idf_py_path, '--version', '@file_args_expansion_inputs/args_a', '@file_args_expansion_inputs/args_b'],
                env=os.environ,
                stderr=subprocess.STDOUT).decode('utf-8', 'ignore')
            self.assertIn('Running: idf.py --version DAAA DBBB DCCC DDDD', output)
        except subprocess.CalledProcessError as e:
            self.fail(f'Process should have exited normally, but it exited with a return code of {e.returncode}')

    def test_recursive_expansion(self):
        """Test recursive expansion of @filename arguments"""
        try:
            output = subprocess.check_output(
                [sys.executable, idf_py_path, '--version', '@file_args_expansion_inputs/args_recursive'],
                env=os.environ,
                stderr=subprocess.STDOUT).decode('utf-8', 'ignore')
            self.assertIn('Running: idf.py --version DAAA DBBB DEEE DFFF', output)
        except subprocess.CalledProcessError as e:
            self.fail(f'Process should have exited normally, but it exited with a return code of {e.returncode}')

    def test_circular_dependency(self):
        """Test circular dependency detection in file argument expansion"""
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            subprocess.check_output(
                [sys.executable, idf_py_path, '--version', '@file_args_expansion_inputs/args_circular_a'],
                env=os.environ,
                stderr=subprocess.STDOUT).decode('utf-8', 'ignore')
        self.assertIn('Circular dependency in file argument expansion', cm.exception.output.decode('utf-8', 'ignore'))

    def test_missing_file(self):
        """Test missing file detection in file argument expansion"""
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            subprocess.check_output(
                [sys.executable, idf_py_path, '--version', '@args_non_existent'],
                env=os.environ,
                stderr=subprocess.STDOUT).decode('utf-8', 'ignore')
        self.assertIn('(expansion of @args_non_existent) could not be opened', cm.exception.output.decode('utf-8', 'ignore'))


class TestWrapperCommands(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_project_dir = os.path.join(current_dir, '..', 'test_build_system', 'build_test_app')
        os.chdir(cls.sample_project_dir)
        super().setUpClass()

    def call_command(self, command: List[str]) -> str:
        try:
            output = subprocess.check_output(
                command,
                env=os.environ,
                stderr=subprocess.STDOUT).decode('utf-8', 'ignore')
            return output
        except subprocess.CalledProcessError as e:
            self.fail(f'Process should have exited normally, but it exited with a return code of {e.returncode}')

    @classmethod
    def tearDownClass(cls):
        subprocess.run([sys.executable, idf_py_path, 'fullclean'], stdout=subprocess.DEVNULL)
        os.chdir(current_dir)
        super().tearDownClass()


class TestUF2Commands(TestWrapperCommands):
    """
    Test if uf2 commands are invoked as expected.
    This test is not testing the functionality of mkuf2.py/idf.py uf2, but the invocation of the command from idf.py.
    """

    def test_uf2(self):
        uf2_command = [sys.executable, idf_py_path, 'uf2']
        output = self.call_command(uf2_command)
        self.assertIn('Executing:', output)

    def test_uf2_with_envvars(self):
        # Values do not really matter, they should not be used.
        os.environ['ESPBAUD'] = '115200'
        os.environ['ESPPORT'] = '/dev/ttyUSB0'
        self.test_uf2()
        os.environ.pop('ESPBAUD')
        os.environ.pop('ESPPORT')

    def test_uf2_app(self):
        uf2_app_command = [sys.executable, idf_py_path, 'uf2-app']
        output = self.call_command(uf2_app_command)
        self.assertIn('Executing:', output)

    def test_uf2_app_with_envvars(self):
        # Values do not really matter, they should not be used.
        os.environ['ESPBAUD'] = '115200'
        os.environ['ESPPORT'] = '/dev/ttyUSB0'
        self.test_uf2_app()
        os.environ.pop('ESPBAUD')
        os.environ.pop('ESPPORT')


if __name__ == '__main__':
    main()
