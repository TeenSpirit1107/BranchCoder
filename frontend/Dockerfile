# Use Node.js as base image
FROM node:18-alpine as build-stage

# Set working directory
WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy package.json and pnpm-lock.yaml files
COPY package.json pnpm-lock.yaml ./

# Install project dependencies
RUN pnpm install --frozen-lockfile

# Copy project files
COPY . .

# Build application - skip type checking
RUN pnpm run build

# Use nginx as production environment image
FROM nginx:stable-alpine as production-stage

# Copy built files to nginx
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf.template

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port 80
EXPOSE 80

# Start nginx with environment variable substitution
CMD ["/docker-entrypoint.sh"] 