#!/usr/bin/env python3
"""
Build linux/amd64 images, push to ECR, and start App Runner deployments.

Requires: Docker (buildx), AWS CLI v2, credentials with ecr:* and apprunner:*.

Frontend NEXT_PUBLIC_* (build args; must match App Runner runtime for the frontend service):
  • Set in the environment, and/or
  • Put them in deploy/frontend-build.env (see deploy/frontend-build.env.example).
  Shell exports override the file. Do not use frontend/.env.production for image builds if it still
  points at localhost — use deploy/frontend-build.env so release builds stay aligned with App Runner
  without repeating fixes.

Environment (optional):
  AWS_REGION (default us-east-1)
  ECR_REGISTRY — full host, e.g. 123456789012.dkr.ecr.us-east-1.amazonaws.com
    If unset, derived from: aws sts get-caller-identity + region
  IMAGE_TAG (default amd64)
  APP_RUNNER_BACKEND_ARN
  APP_RUNNER_FRONTEND_ARN

Examples:
  cp deploy/frontend-build.env.example deploy/frontend-build.env   # edit once
  ./scripts/deploy_app_runner.py --frontend

  # or per session:
  export NEXT_PUBLIC_API_URL=https://xxxx.awsapprunner.com
  export NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
  export NEXT_PUBLIC_CLERK_PREMIUM_PLAN_KEY=emet_subscription
  ./scripts/deploy_app_runner.py --backend --frontend
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

FRONTEND_PUBLIC_KEYS = (
    "NEXT_PUBLIC_API_URL",
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
    "NEXT_PUBLIC_CLERK_PREMIUM_PLAN_KEY",
)


def load_env_file(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "=" not in s:
                continue
            key, _, val = s.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                out[key] = val
    return out


def resolve_frontend_public_env(repo_root: str, env_file: str | None) -> dict[str, str]:
    """Shell env wins over file(s). Loads deploy/frontend-build.env then optional --frontend-env-file."""
    merged: dict[str, str] = {}
    default = os.path.join(repo_root, "deploy", "frontend-build.env")
    if os.path.isfile(default):
        merged.update(load_env_file(default))
    if env_file:
        if not os.path.isfile(env_file):
            print(f"Missing file: {env_file}", file=sys.stderr)
            sys.exit(1)
        merged.update(load_env_file(env_file))
    result: dict[str, str] = {}
    for k in FRONTEND_PUBLIC_KEYS:
        v = os.environ.get(k, "").strip() or merged.get(k, "").strip()
        result[k] = v
    return result


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, env={**os.environ, **(env or {})})
    if r.returncode != 0:
        sys.exit(r.returncode)


def aws_json(args: list[str]) -> str:
    r = subprocess.run(
        ["aws", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout.strip()


def ecr_registry(region: str) -> str:
    explicit = os.environ.get("ECR_REGISTRY", "").strip()
    if explicit:
        return explicit.rstrip("/")
    account = aws_json(
        [
            "sts",
            "get-caller-identity",
            "--region",
            region,
            "--query",
            "Account",
            "--output",
            "text",
        ]
    )
    return f"{account}.dkr.ecr.{region}.amazonaws.com"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", action="store_true")
    parser.add_argument("--frontend", action="store_true")
    parser.add_argument(
        "--frontend-env-file",
        metavar="PATH",
        default=None,
        help="Optional KEY=VALUE file; merged after deploy/frontend-build.env (still overridden by shell).",
    )
    args = parser.parse_args()
    if not args.backend and not args.frontend:
        args.backend = args.frontend = True

    region = os.environ.get("AWS_REGION", "us-east-1")
    tag = os.environ.get("IMAGE_TAG", "amd64").strip() or "amd64"
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    registry = ecr_registry(region)

    # docker login pipe - use subprocess with stdin
    pw_proc = subprocess.run(
        ["aws", "ecr", "get-login-password", "--region", region],
        capture_output=True,
        check=True,
    )
    print("+ docker login ...", flush=True)
    subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        input=pw_proc.stdout,
        check=True,
    )

    if args.backend:
        img = f"{registry}/emet-backend:{tag}"
        run(
            [
                "docker",
                "buildx",
                "build",
                "--platform",
                "linux/amd64",
                "--provenance=false",
                "-f",
                os.path.join(repo_root, "backend", "Dockerfile"),
                "-t",
                img,
                "--push",
                os.path.join(repo_root, "backend"),
            ]
        )

    if args.frontend:
        pub = resolve_frontend_public_env(repo_root, args.frontend_env_file)
        for k in FRONTEND_PUBLIC_KEYS:
            if not pub[k]:
                print(
                    f"Missing {k} — set in shell or deploy/frontend-build.env (see deploy/frontend-build.env.example).",
                    file=sys.stderr,
                )
                sys.exit(1)
        api_url = pub["NEXT_PUBLIC_API_URL"]
        allow_local = os.environ.get("ALLOW_LOCAL_API_URL_FOR_IMAGE", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if not allow_local and (
            "localhost" in api_url.lower() or "127.0.0.1" in api_url
        ):
            print(
                "NEXT_PUBLIC_API_URL points at localhost — unsafe for a pushed image. "
                "Fix deploy/frontend-build.env or exports, or set ALLOW_LOCAL_API_URL_FOR_IMAGE=1 to override.",
                file=sys.stderr,
            )
            sys.exit(1)
        img = f"{registry}/emet-frontend:{tag}"
        run(
            [
                "docker",
                "buildx",
                "build",
                "--platform",
                "linux/amd64",
                "--provenance=false",
                "-f",
                os.path.join(repo_root, "frontend", "Dockerfile"),
                "--build-arg",
                f"NEXT_PUBLIC_API_URL={pub['NEXT_PUBLIC_API_URL']}",
                "--build-arg",
                f"NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY={pub['NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY']}",
                "--build-arg",
                f"NEXT_PUBLIC_CLERK_PREMIUM_PLAN_KEY={pub['NEXT_PUBLIC_CLERK_PREMIUM_PLAN_KEY']}",
                "-t",
                img,
                "--push",
                os.path.join(repo_root, "frontend"),
            ]
        )

    for key, arn_env in (
        ("backend", "APP_RUNNER_BACKEND_ARN"),
        ("frontend", "APP_RUNNER_FRONTEND_ARN"),
    ):
        if not ((args.backend and key == "backend") or (args.frontend and key == "frontend")):
            continue
        arn = os.environ.get(arn_env, "").strip()
        if not arn:
            print(
                f"Skip App Runner start ({key}): set {arn_env} to your service ARN.",
                flush=True,
            )
            continue
        run(
            [
                "aws",
                "apprunner",
                "start-deployment",
                "--service-arn",
                arn,
                "--region",
                region,
            ]
        )


if __name__ == "__main__":
    main()
