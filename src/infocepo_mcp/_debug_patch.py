"""Patch MCP SDK runner.py to log debug info for -32602 issue."""
import os, shutil

runner = "/usr/local/lib/python3.12/site-packages/mcp/server/runner.py"
cache_dir = "/usr/local/lib/python3.12/site-packages/mcp/server/__pycache__"

if not os.path.exists(runner):
    print(f"[PATCH] runner.py not found at {runner}, skipping")
    exit()

with open(runner, "r") as f:
    content = f.read()

if "[DBG_PATCH]" in content:
    print("[PATCH] runner.py already patched, skipping")
else:
    # Inject debug after "method, params = ctx.method, ctx.params"
    old1 = (
        "            method, params = ctx.method, ctx.params\n"
        "            # Pinned compat: spec methods are surface-validated before lookup,"
    )
    new1 = (
        "            method, params = ctx.method, ctx.params\n"
        "            # DBG_PATCH\n"
        "            import sys as _dbg\n"
        '            print("[DBG] method=" + repr(method) + " init_accepted=" + str(self.connection.initialize_accepted), file=_dbg.stderr, flush=True)\n'
        "            # Pinned compat: spec methods are surface-validated before lookup,"
    )
    if old1 not in content:
        print("[PATCH] WARNING: old1 not found in runner.py")
    else:
        content = content.replace(old1, new1, 1)
        print("[PATCH] Injected method debug")

    # Inject debug before INVALID_PARAMS raise in _inner function
    old2 = (
        "            if not self.connection.initialize_accepted and method not in _INIT_EXEMPT:\n"
        "                # Pinned compat: the same error shape the union validation produced.\n"
        '                raise MCPError(code=INVALID_PARAMS, message="Invalid request parameters", data="")'
    )
    new2 = (
        "            if not self.connection.initialize_accepted and method not in _INIT_EXEMPT:\n"
        "                print('[DBG] init_accepted=False -> INVALID_PARAMS', file=_dbg.stderr, flush=True)\n"
        "                # Pinned compat: the same error shape the union validation produced.\n"
        '                raise MCPError(code=INVALID_PARAMS, message="Invalid request parameters", data="")'
    )
    if old2 not in content:
        print("[PATCH] WARNING: old2 not found in runner.py")
    else:
        content = content.replace(old2, new2, 1)
        print("[PATCH] Injected init_accepted debug")

    # Inject debug before params_type.model_validate
    old3 = (
        "            typed_params = entry.params_type.model_validate({} if params is None else params, by_name=False)\n"
        "            result = await entry.handler(ctx, typed_params)"
    )
    new3 = (
        "            try:\n"
        "                typed_params = entry.params_type.model_validate({} if params is None else params, by_name=False)\n"
        "            except Exception as _mpve:\n"
        '                print("[DBG] model_validate FAIL: " + type(_mpve).__name__ + ": " + str(_mpve), file=_dbg.stderr, flush=True)\n'
        '                raise MCPError(code=INVALID_PARAMS, message="model_validate fail: " + str(_mpve), data="") from None\n'
        "            result = await entry.handler(ctx, typed_params)"
    )
    if old3 not in content:
        print("[PATCH] WARNING: old3 not found in runner.py")
    else:
        content = content.replace(old3, new3, 1)
        print("[PATCH] Injected model_validate debug")

    with open(runner, "w") as f:
        f.write(content)

# Clear __pycache__
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)
    print("[PATCH] __pycache__ cleared")
print("[PATCH] done")
