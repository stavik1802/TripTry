# TripPlanner Frontend

A modern React-based frontend for the TripPlanner application, built with TypeScript, Vite, and Tailwind CSS.

## 🚀 Features

- **Modern React 18** with TypeScript for type safety
- **Vite** for fast development and optimized builds
- **Tailwind CSS** for responsive, utility-first styling
- **Multi-session support** for managing multiple trip planning sessions
- **Real-time updates** with WebSocket-like polling
- **Responsive design** that works on desktop and mobile
- **Dark/Light mode** support (planned)

## 🛠️ Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety and better DX
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling framework
- **ESLint** - Code linting
- **PostCSS** - CSS processing

## 📦 Installation

```bash
# Install dependencies
npm install

# Or use npm ci for production builds
npm ci
```

## 🏃‍♂️ Development

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

## 🌐 Environment Configuration

The frontend automatically detects the API URL based on the environment:

- **Development**: `http://localhost:8000`
- **Production**: Uses the Elastic Beanstalk URL automatically

### Manual Configuration (if needed)

```bash
# Development only
VITE_API_BASE=http://localhost:8000

# Production (usually not needed)
VITE_API_BASE=https://your-app.region.elasticbeanstalk.com
```

## 📁 Project Structure

```
trip_ui/
├── src/
│   ├── App.tsx              # Main application component
│   ├── MultiSessionApp.tsx  # Multi-session management
│   ├── main.tsx            # Application entry point
│   ├── App.css             # Global styles
│   ├── index.css           # Tailwind imports
│   └── assets/             # Static assets
├── public/                 # Public assets
├── dist/                   # Production build output
├── index.html              # HTML template
├── package.json            # Dependencies and scripts
├── vite.config.ts          # Vite configuration
├── tailwind.config.js      # Tailwind configuration
├── postcss.config.js       # PostCSS configuration
├── eslint.config.js        # ESLint configuration
└── tsconfig.json           # TypeScript configuration
```

## 🔧 Configuration Files

### Vite Configuration (`vite.config.ts`)
- Development server settings
- Build optimization
- Proxy configuration for API calls

### Tailwind Configuration (`tailwind.config.js`)
- Custom color palette
- Responsive breakpoints
- Component styling

### TypeScript Configuration (`tsconfig.json`)
- Strict type checking
- Path mapping
- Build target settings

## 🚀 Deployment

The frontend is automatically built and deployed with the backend via the main `deploy-eb.sh` script:

```bash
# From project root
./deploy-eb.sh
```

### Manual Frontend Deployment

```bash
# Build for production
npm run build

# The dist/ folder contains the production build
# This is automatically served by the backend in production
```

## 🎨 Styling

The application uses Tailwind CSS for styling:

- **Utility-first approach** for rapid development
- **Responsive design** with mobile-first breakpoints
- **Custom color palette** defined in `tailwind.config.js`
- **Component-based styling** with reusable classes

### Key Styling Patterns

```tsx
// Responsive design
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

// Dark mode support (planned)
<div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-white">

// Interactive states
<button className="bg-blue-500 hover:bg-blue-600 focus:ring-2 focus:ring-blue-500">
```

## 🔍 Development Tips

### Hot Module Replacement (HMR)
Vite provides instant HMR for fast development:
- Changes to React components update instantly
- CSS changes apply without page refresh
- TypeScript errors show in browser console

### API Integration
The frontend communicates with the backend via REST API:
- All API calls are made to `/api/*` endpoints
- Error handling with user-friendly messages
- Loading states for better UX

### State Management
Currently uses React's built-in state management:
- `useState` for component state
- `useEffect` for side effects
- Props drilling for data flow

## 🐛 Troubleshooting

### Common Issues

**Build fails with TypeScript errors:**
```bash
# Check TypeScript configuration
npm run build --verbose
```

**Styling not applying:**
```bash
# Ensure Tailwind is properly configured
npm run dev
# Check browser dev tools for CSS loading
```

**API calls failing:**
```bash
# Verify backend is running
curl http://localhost:8000/health
# Check network tab in browser dev tools
```

### Performance Optimization

- **Code splitting** - Vite automatically splits code by route
- **Tree shaking** - Unused code is eliminated in production
- **Asset optimization** - Images and fonts are optimized
- **Bundle analysis** - Use `npm run build --analyze` to analyze bundle size

## 📚 Additional Resources

- [React Documentation](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Vite Guide](https://vitejs.dev/guide/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [ESLint Configuration](https://eslint.org/docs/latest/use/configure/)

## 🤝 Contributing

1. Follow the existing code style
2. Use TypeScript for all new components
3. Add proper error handling
4. Test on multiple screen sizes
5. Ensure accessibility standards

## 📄 License

This project is part of the TripPlanner application. See the main project README for license information.