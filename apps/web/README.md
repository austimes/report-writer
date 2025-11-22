# Report Writer Web App

Frontend web application for the Report Writer project.

## Tech Stack

- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Backend**: Convex
- **Routing**: React Router v6
- **Styling**: Tailwind CSS + Radix UI
- **Markdown**: react-markdown + remark-gfm

## Directory Structure

```
src/
├── app/              # Application shell and routing
│   └── pages/        # Page components
├── features/         # Feature modules
│   ├── auth/         # Authentication
│   ├── projects/     # Project management
│   ├── editor/       # Document editor
│   ├── comments/     # Comments system
│   ├── locks/        # Editing locks
│   ├── versions/     # Version control
│   └── agentThreads/ # AI agent integration
├── shared/           # Shared code
│   ├── components/   # Reusable UI components
│   ├── hooks/        # Custom React hooks
│   └── utils/        # Utility functions
└── lib/              # Third-party integrations
    └── convexClient.ts
```

## Development

### Prerequisites

- Node.js 18+
- npm or pnpm

### Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Create `.env` file from example:
   ```bash
   cp .env.example .env
   ```

3. Update `VITE_CONVEX_URL` in `.env` with your Convex deployment URL

### Running

Start the development server:
```bash
npm run dev
```

The app will be available at http://localhost:3000

### Building

Build for production:
```bash
npm run build
```

Preview production build:
```bash
npm run preview
```

## Routes

- `/` - Home page / Projects list
- `/login` - Login page
- `/signup` - Sign up page
- `/projects/:id` - Project editor

## Components

Shared UI components are located in `src/shared/components/ui/`:
- `Button` - Button component with variants
- `Input` - Text input component
- `Card` - Card container components

Components use Radix UI primitives and are styled with Tailwind CSS.
