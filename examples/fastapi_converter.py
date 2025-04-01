"""Example demonstrating FastAPI to FlashMCP conversion."""

from fastapi import FastAPI, Body, Path
from pydantic import BaseModel
from typing import List, Optional

from FlashMCP.convert.fastapi import fastapi_to_FlashMCP


# Create a sample FastAPI app
app = FastAPI(title="Todo API")


class TodoItem(BaseModel):
    """A simple todo item."""

    id: Optional[int] = None
    title: str
    description: str
    completed: bool = False


# In-memory database
todos = {}
todo_id_counter = 1


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    """Retrieve all todo items."""
    return list(todos.values())


@app.get("/todos/{todo_id}", response_model=TodoItem)
async def get_todo(todo_id: int = Path(..., description="The ID of the todo item")):
    """Retrieve a specific todo item by ID."""
    if todo_id not in todos:
        return {"error": f"Todo {todo_id} not found"}
    return todos[todo_id]


@app.post("/todos", response_model=TodoItem)
async def create_todo(
    todo: TodoItem = Body(..., description="The todo item to create"),
):
    """Create a new todo item."""
    global todo_id_counter
    todo.id = todo_id_counter
    todos[todo_id_counter] = todo
    todo_id_counter += 1
    return todo


@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(
    todo_id: int = Path(..., description="The ID of the todo item"),
    todo: TodoItem = Body(..., description="The updated todo item"),
):
    """Update an existing todo item."""
    if todo_id not in todos:
        return {"error": f"Todo {todo_id} not found"}

    todo.id = todo_id
    todos[todo_id] = todo
    return todo


@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int = Path(..., description="The ID of the todo item")):
    """Delete a todo item."""
    if todo_id not in todos:
        return {"error": f"Todo {todo_id} not found"}

    del todos[todo_id]
    return {"message": f"Todo {todo_id} deleted"}


# Convert the FastAPI app to a FlashMCP server
mcp = fastapi_to_FlashMCP(app)


if __name__ == "__main__":
    # Run the FlashMCP server
    mcp.run()

    # Alternatively, you can run the original FastAPI app with uvicorn:
    # import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000)
