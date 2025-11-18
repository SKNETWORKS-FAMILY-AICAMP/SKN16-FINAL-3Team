FROM node:18-alpine

WORKDIR /app

# Copy package files first for better Docker layer caching
COPY package.json package-lock.json* ./

# Install dependencies
# npm ci is faster and more reliable for production builds
# Falls back to npm install if package-lock.json is missing
RUN if [ -f package-lock.json ]; then \
      npm ci --legacy-peer-deps; \
    else \
      npm install --legacy-peer-deps; \
    fi

# Verify critical dependencies are installed
RUN npm list react-markdown remark-gfm || npm install react-markdown remark-gfm --legacy-peer-deps

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Default command (can be overridden in docker-compose.yml)
CMD ["npm", "run", "dev"]





