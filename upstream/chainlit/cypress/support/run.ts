import {
  ChildProcessWithoutNullStreams,
  SpawnOptionsWithoutStdio,
  spawn,
  spawnSync
} from 'child_process';
import { access } from 'fs/promises';
import { dirname, join, delimiter } from 'path';

let fallbackDependenciesInstalled = false;

export const runChainlit = async (
  spec: Cypress.Spec | null = null
): Promise<ChildProcessWithoutNullStreams> => {
  const CHAILIT_DIR = join(process.cwd(), 'backend', 'chainlit');

  const backendDir = join(process.cwd(), 'backend');

  return new Promise((resolve, reject) => {
    const testDir = spec ? dirname(spec.absolute) : CHAILIT_DIR;
    const entryPointFileName = spec
      ? spec.name.startsWith('async')
        ? 'main_async.py'
        : spec.name.startsWith('sync')
        ? 'main_sync.py'
        : 'main.py'
      : 'hello.py';

    const entryPointPath = join(testDir, entryPointFileName);

    if (!access(entryPointPath)) {
      return reject(
        new Error(`Entry point file does not exist: ${entryPointPath}`)
      );
    }

    const env: NodeJS.ProcessEnv = {
      ...process.env,
      CHAINLIT_APP_ROOT: testDir
    };

    let command = 'uv';
    let args: string[] = [
      '--project',
      CHAILIT_DIR,
      'run',
      'chainlit',
      'run',
      entryPointPath,
      '-h',
      '--ci'
    ];

    const uvCheck = spawnSync(command, ['--version'], { stdio: 'ignore' });
    const uvUnavailable = Boolean(uvCheck.error) || uvCheck.status !== 0;

    if (uvUnavailable) {
      command = process.env.CHAINLIT_PYTHON_BIN
        ? process.env.CHAINLIT_PYTHON_BIN
        : process.platform === 'win32'
        ? 'python'
        : 'python3';
      args = ['-m', 'chainlit.cli', 'run', entryPointPath, '-h', '--ci'];
      env.PYTHONPATH = env.PYTHONPATH
        ? `${backendDir}${delimiter}${env.PYTHONPATH}`
        : backendDir;

      if (!fallbackDependenciesInstalled) {
        const installResult = spawnSync(
          command,
          ['-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', '-e', backendDir],
          {
            env,
            stdio: 'inherit'
          }
        );

        if (installResult.status !== 0) {
          return reject(
            `Failed to install Chainlit backend dependencies with ${command}.`
          );
        }

        fallbackDependenciesInstalled = true;
      }
    }

    const options: SpawnOptionsWithoutStdio = {
      env
    };

    const chainlit = spawn(command, args, options);

    chainlit.stdout.on('data', (data) => {
      const output = data.toString();
      if (output.includes('Your app is available at')) {
        resolve(chainlit);
      }
    });

    chainlit.stderr.on('data', (data) => {
      console.error(`[Chainlit stderr] ${data}`);
    });

    chainlit.on('error', (error) => {
      reject(error.message);
    });

    chainlit.on('exit', function (code) {
      reject('Chainlit process exited with code ' + code);
    });
  });
};
