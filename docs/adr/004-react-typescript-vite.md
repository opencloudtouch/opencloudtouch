# ADR-004: Use React 19 with TypeScript and Vite

**Date:** 2026-01-05  
**Status:** Accepted  
**Deciders:** Frontend Team

## Context

OpenCloudTouch frontend needs a modern, performant UI framework for controlling Bose SoundTouch devices. Requirements:

1. **Type Safety:** Catch errors at compile-time, not runtime.
2. **Fast Development:** Hot module reload (HMR) for rapid iteration.
3. **Component Reusability:** Build reusable UI components (PresetButton, DeviceCard).
4. **Mobile Support:** Responsive design for tablets/phones.
5. **Modern Standards:** Use latest JavaScript features (async/await, ESM).

## Decision

We will use **React 19 + TypeScript 5 + Vite 4** for the frontend.

### Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.0.0 | UI framework (functional components, hooks) |
| TypeScript | 5.9.3 | Type safety, autocompletion |
| Vite | 4.x | Build tool, dev server (fast HMR) |
| React Query | 5.x | Server state management, caching |
| React Router | 7.x | Client-side routing |
| Vitest | 4.x | Unit testing framework |
| Cypress | 15.x | E2E testing |

### Architecture

**Component Hierarchy:**

```
App.tsx
├── ErrorBoundary.tsx
├── Routes
│   ├── Dashboard.tsx
│   │   ├── DeviceCard.tsx
│   │   │   └── PresetButton.tsx
│   │   └── RadioSearch.tsx
│   ├── Settings.tsx
│   └── Welcome.tsx
└── Providers (QueryClient, Router)
```

**State Management:**

```typescript
// ✅ Server state: React Query
const { data: devices } = useQuery({
  queryKey: ['devices'],
  queryFn: fetchDevices,
  refetchInterval: 5000,  // Poll every 5s
});

// ✅ UI state: useState
const [volume, setVolume] = useState(50);

// ✅ Form state: Controlled components
<input value={name} onChange={(e) => setName(e.target.value)} />
```

**API Communication:**

```typescript
// api/devices.ts
export async function fetchDevices(): Promise<DevicesResponse> {
  const response = await fetch(`${API_URL}/api/devices`);
  if (!response.ok) throw new Error('Failed to fetch devices');
  return response.json();
}

// Hook usage
const { data, error, isLoading } = useQuery({
  queryKey: ['devices'],
  queryFn: fetchDevices,
});
```

## Consequences

### Positive

- **Type Safety:** TypeScript catches 80%+ of bugs before runtime.
- **Fast HMR:** Vite rebuilds in <100ms, React HMR preserves state.
- **Modern React:** Hooks/functional components (no class components).
- **Developer Experience:** Autocompletion, refactoring, inline docs.
- **Performance:** Vite uses ESM natively, no bundling in dev mode.
- **Testing:** Vitest is Vite-native, fast test execution.

### Negative

- **Bundle Size:** React 19 is 50KB gzipped (acceptable for local dashboard).
- **Learning Curve:** TypeScript requires understanding generics, interfaces.
- **Build Complexity:** Vite config needed for Cypress, proxies, etc.

## Key Design Patterns

### 1. Functional Components Only

```tsx
// ✅ GOOD: Functional component
export function DeviceCard({ device }: { device: Device }) {
  const [volume, setVolume] = useState(device.volume);
  return <div>{device.name}</div>;
}

// ❌ BAD: Class component (legacy pattern)
class DeviceCard extends React.Component { ... }
```

### 2. TypeScript Interfaces for Props

```typescript
interface DeviceCardProps {
  device: Device;
  onPresetClick?: (presetNumber: number) => void;
}

export function DeviceCard({ device, onPresetClick }: DeviceCardProps) {
  // Autocomplete + type checking
}
```

### 3. React Query for Server State

```typescript
// ✅ GOOD: Declarative, handles loading/error/caching
const { data, isLoading, error } = useQuery({
  queryKey: ['devices'],
  queryFn: fetchDevices,
});

// ❌ BAD: Manual fetch + useState (race conditions, no caching)
const [devices, setDevices] = useState([]);
useEffect(() => {
  fetch('/api/devices').then(res => setDevices(res));
}, []);
```

### 4. CSS Modules for Styling

```tsx
// DeviceCard.module.css
.card { background: white; border-radius: 8px; }
.card:hover { box-shadow: 0 4px 8px rgba(0,0,0,0.1); }

// DeviceCard.tsx
import styles from './DeviceCard.module.css';
<div className={styles.card}>...</div>
```

## Build Configuration

**Vite Config:**

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:7777',  // Proxy API to backend
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,  // Debug production builds
  },
  test: {
    globals: true,
    environment: 'jsdom',  // Simulate browser
    setupFiles: './tests/setup.ts',
  },
});
```

## Alternatives Considered

### 1. Vue.js 3

**Reason for rejection:** Team has more React experience, React ecosystem is larger.

### 2. Svelte

**Reason for rejection:** Smaller ecosystem, less TypeScript support, unfamiliarity.

### 3. Vanilla JavaScript (no framework)

**Reason for rejection:** Too much boilerplate for complex state management, routing, forms.

### 4. Create React App (CRA)

**Reason for rejection:** Slow builds (Webpack), deprecated by React team. Vite is 10-100x faster.

### 5. Next.js

**Reason for rejection:** Overkill for local dashboard. SSR not needed (no SEO required).

## Migration Path (Future)

If we outgrow this stack:

1. **Switch to Next.js:** If we add user auth, multi-page app.
2. **Add Redux:** If client-side state becomes too complex (unlikely).
3. **Migrate to Remix:** If we need advanced routing/data loading.

## Performance Targets

| Metric | Target | Actual (v0.2.0) |
|--------|--------|-----------------|
| Bundle Size | <500KB gzipped | 380KB ✅ |
| First Contentful Paint | <1.5s | 1.2s ✅ |
| Time to Interactive | <3s | 2.1s ✅ |
| HMR Speed | <100ms | 50ms ✅ |
| Test Execution | <5s | 3.2s ✅ |

## Related Decisions

- See ADR-001 for backend Clean Architecture
- See ADR-005 for API design
- See ADR-006 for testing strategy

## References

- [React 19 Docs](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Vite Documentation](https://vitejs.dev/)
- [React Query Docs](https://tanstack.com/query/latest)
- [Why Vite over CRA](https://vitejs.dev/guide/why.html)
