"""Quiesced local backup plus restore into an isolated temporary database."""

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    "docker",
    "compose",
    "--project-directory",
    str(ROOT / "deploy/weknora"),
    "-p",
    "docagent",
]


def run(args, **kwargs):
    return subprocess.run(args, check=True, timeout=180, **kwargs)


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = ROOT / ".runtime/backups" / stamp
    folder.mkdir(parents=True)
    restored = False
    run(COMPOSE + ["stop", "app", "studio"])
    try:
        user = run(
            ["docker", "exec", "WeKnora-postgres", "printenv", "POSTGRES_USER"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        db = run(
            ["docker", "exec", "WeKnora-postgres", "printenv", "POSTGRES_DB"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        with (folder / "database.dump").open("wb") as out:
            run(
                ["docker", "exec", "WeKnora-postgres", "pg_dump", "-U", user, "-d", db, "-Fc"],
                stdout=out,
            )
        # The run container is disposable, so export the snapshot directly from its stdout.
        script = "import sqlite3,sys; src=sqlite3.connect('/data/studio.sqlite3'); dst=sqlite3.connect('/tmp/snapshot'); src.backup(dst); dst.close(); src.close(); sys.stdout.buffer.write(open('/tmp/snapshot','rb').read())"
        with (folder / "studio.sqlite3").open("wb") as out:
            run(
                COMPOSE
                + [
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "--entrypoint",
                    "/app/.venv/bin/python",
                    "studio",
                    "-c",
                    script,
                ],
                stdout=out,
            )
        mounts = json.loads(
            run(
                ["docker", "inspect", "WeKnora-app"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout
        )[0]["Mounts"]
        volume = next(m["Name"] for m in mounts if m["Destination"] == "/data/files")
        script = "import tarfile,sys; t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz'); t.add('/source',arcname='files'); t.close()"
        with (folder / "files.tar.gz").open("wb") as out:
            run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network=none",
                    "--mount",
                    f"type=volume,source={volume},target=/source,readonly",
                    "python:3.12-alpine",
                    "python",
                    "-c",
                    script,
                ],
                stdout=out,
            )
        shutil.copyfile(ROOT / "deploy/weknora/.env", folder / "deployment.env")
        shutil.copyfile(ROOT / ".runtime/runner.key", folder / "runner.key")
        tempdb = "qa_restore_" + secrets.token_hex(5)
        run(["docker", "exec", "WeKnora-postgres", "createdb", "-U", user, tempdb])
        try:
            with (folder / "database.dump").open("rb") as stream:
                run(
                    [
                        "docker",
                        "exec",
                        "-i",
                        "WeKnora-postgres",
                        "pg_restore",
                        "--exit-on-error",
                        "--no-owner",
                        "--no-privileges",
                        "-U",
                        user,
                        "-d",
                        tempdb,
                    ],
                    stdin=stream,
                )
            count = run(
                [
                    "docker",
                    "exec",
                    "WeKnora-postgres",
                    "psql",
                    "-U",
                    user,
                    "-d",
                    tempdb,
                    "-Atc",
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'",
                ],
                capture_output=True,
                text=True,
            ).stdout.strip()
            restored = int(count) > 0
        finally:
            run(["docker", "exec", "WeKnora-postgres", "dropdb", "-U", user, tempdb])
        checksums = {
            f.name: hashlib.sha256(f.read_bytes()).hexdigest()
            for f in folder.iterdir()
            if f.is_file()
        }
        (folder / "manifest.json").write_text(json.dumps(checksums, indent=2))
        report = {
            "timestamp_utc": stamp,
            "quiesced": True,
            "database_restore_into_isolated_db": restored,
            "restored_public_tables": int(count),
            "backup_files": list(checksums),
            "private_backup_directory": str(folder),
            "file_volume_and_studio_exported": True,
            "production_restore_performed": False,
        }
        (ROOT / "docs/evidence/backup-acceptance.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        run(COMPOSE + ["up", "-d", "--no-build", "app", "studio", "frontend"])
        run(COMPOSE + ["restart", "frontend"])
    if not restored:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
