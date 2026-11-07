# implementation

I would probably start with the bear minimum that allows ingestion and consultation on a local device
I would like to "ship it" (for me) as a thing that can be installed, meaning I would like to avoid growing it from inside a vault, but still I need to iterate quite fast multiple times.
It's the equivalent of installing a python package using the sources, and changing them from the installed package.
With the features described here, and an obsidian vault, possibly empty, we can start ingesting data, and progressively reorganise.
Alternatively, the process is to "install" the LLM and visualisation plugin in existing vaults that need restructuring and run the ingestion on all notes

## data structure and skills

- a well defined set of frontmatter fields (that can potentially change as the project evolves) and folder structure
- an LLM command that intializes the obsidian vault (creates the contributing.md? injects the skills?)
- an LLM process to ingest + access data, probably as a plugin of the vault
- a minimal set of (agentic) tools to ingest external feeds (e.g. oura API)
- these skills should probably live inside the vault?

## visualisation

- an obsidian visualisation plugin, this is the main coding piece, shows things in a timeline, enables to filter, show/hide, etc.

## logging & versioning

- possibly managed as a git repository so content creation retains history 


problem: obsidian and git are very good at light text-based content, less so with images

next iteration would be to put this online, accessible via web / mobile

## what already exists

for obsidian

- https://github.com/pengd0t/TimelineLayout timeline layout for obsidian, probably the closest to what I'm thinking
- other plugins explored (like timelink and chronos) look more like yet other project management tools with gantt charts and kanban boards
- other plugins explored (like excalidraw and juggl) look overcomplicated drawing mechanisms mocking figma, not the thing I'm looking for

other data visualisation

- kronograph by cambridge intelligence seems related https://cambridge-intelligence.com/kronograph/