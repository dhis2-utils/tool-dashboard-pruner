/** @type {import('@dhis2/cli-app-scripts').D2Config} */
const config = {
    type: 'app',
    // The app key: the repo name. Never change it again: user roles grant
    // access to the app through an authority named after it.
    name: 'tool-dashboard-pruner',
    title: 'Dashboard Pruner Tool',
    description:
        'Find dashboards that are empty or not viewed in a year, and delete them',
    author: {
        name: 'HISP Centre, University of Oslo',
        email: 'dev@dhis2.org',
    },
    minDHIS2Version: '2.40',

    entryPoints: {
        app: './src/App.tsx',
    },

    viteConfigExtensions: './viteConfigExtensions.mts',
}

module.exports = config
