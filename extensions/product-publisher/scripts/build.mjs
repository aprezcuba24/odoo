import { spawn } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.dirname(fileURLToPath(import.meta.url))
const appDir = path.resolve(rootDir, '..')
const watch = process.argv.includes('--watch')

function run(args) {
  return new Promise((resolve, reject) => {
    const child = spawn('npx', ['vite', 'build', ...args], {
      cwd: appDir,
      stdio: 'inherit',
      shell: true,
      env: process.env,
    })
    child.on('exit', (code) => {
      if (code === 0) resolve()
      else reject(new Error(`vite exited with ${code}: ${args.join(' ')}`))
    })
  })
}

async function buildOnce() {
  await run([])
  await run(['--config', 'vite.extension.config.ts'])
  await run(['--config', 'vite.odoo-bridge.config.ts'])
}

if (!watch) {
  await buildOnce()
} else {
  await buildOnce()
  console.info('[product-publisher] watch: rebuilding on change…')

  const { watch: fsWatch } = await import('node:fs')
  let timer = null
  let building = false
  let pending = false

  const schedule = () => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      void (async () => {
        if (building) {
          pending = true
          return
        }
        building = true
        try {
          console.info('[product-publisher] rebuilding…')
          await buildOnce()
          console.info('[product-publisher] rebuild done')
        } catch (err) {
          console.error(err)
        } finally {
          building = false
          if (pending) {
            pending = false
            schedule()
          }
        }
      })()
    }, 300)
  }

  fsWatch(path.resolve(appDir, 'src'), { recursive: true }, schedule)
}
