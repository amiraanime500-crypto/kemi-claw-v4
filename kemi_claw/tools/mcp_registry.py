"""MCP-style tool registry: each tool has a name, description, schema and async fn."""


class MCPRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name, description, schema, fn):
        self._tools[name] = {"description": description, "schema": schema, "fn": fn}

    def manifest(self):
        return [
            {"name": n, "description": t["description"], "schema": t["schema"]}
            for n, t in self._tools.items()
        ]

    async def call(self, name, args):
        if name not in self._tools:
            return {"error": f"unknown tool {name}"}
        return await self._tools[name]["fn"](**(args or {}))


registry = MCPRegistry()
