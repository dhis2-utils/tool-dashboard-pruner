/** @type {import('@dhis2/cli-app-scripts').D2Config} */
const config = {
    type: 'app',
    // Matches the key of the pre-App Platform releases (0.1.x), so installing
    // this version upgrades the existing app instead of adding a second one
    name: 'Dashboard-Pruner-Tool',
    title: 'Dashboard Pruner Tool',
    description:
        'Tool to help you remove unused or empty dashboards from your DHIS2 instance',
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
