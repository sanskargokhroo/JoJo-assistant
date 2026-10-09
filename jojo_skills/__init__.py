"""
📦 JoJo Skills: Dynamic Persistent Custom Tools & Skills Registry
Contains self-synthesized python tools that JoJo has created and verified.
"""

import os
import importlib
import inspect

SKILLS_DIR = os.path.dirname(__file__)

def get_available_skills():
    """Dynamically loads and lists all executable skills in jojo_skills/."""
    skills = {}
    for f in os.listdir(SKILLS_DIR):
        if f.endswith(".py") and not f.startswith("__"):
            mod_name = f[:-3]
            try:
                mod = importlib.import_module(f"jojo_skills.{mod_name}")
                # Reload in case it was updated live
                importlib.reload(mod)
                for name, func in inspect.getmembers(mod, inspect.isfunction):
                    if not name.startswith("_"):
                        skills[f"{mod_name}.{name}"] = {
                            "func": func,
                            "doc": func.__doc__ or "Custom synthesized skill",
                            "module": mod_name
                        }
            except Exception as e:
                print(f"⚠️ Error loading custom skill {f}: {e}")
    return skills
