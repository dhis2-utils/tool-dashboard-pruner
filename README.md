# DHIS2 Dashboard Pruner App

> ![Maturity: Experimental](https://img.shields.io/badge/maturity-Experimental-orange)  
> Intended use: tool to prune dashboards that are empty or have not been actively viewed in the last year.
> Maintainers: HISP Centre implementation team.
>
> **WARNING**  
> This tool is intended to be used by system administrators, not end users. It is available as a DHIS2 app, but has not been through the same rigorous testing as normal core apps. It should be used with care, and always tested in a development environment.

## License
© Copyright University of Oslo 2004-2025. Licensed under BSD-3-Clause. See LICENSE for details.


## About the app

The DHIS2 Dashboard Pruner App is a tool designed to help administrators manage and clean up
their DHIS2 dashboards by removing unused or obsolete dashboard items. This helps in maintaining
an organized and efficient dashboard environment, ensuring that only relevant and necessary items
are retained.

You can choose to remove dashboards which are empty (i.e., contain no dashboard items) or
dashboards which have not been **actively** viewed in over one year. When you delete a dashboard with this app,
the underlying dashboard items are not deleted, only the dashboard itself.

The data statistics system of DHIS2 counts two different types of views of a dashboard:
- Active views: when a user explicitly opens a dashboard in the DHIS2 dashboard app.
- Passive views: when a dashboard is loaded when the user logins to DHIS2, e.g. the default landing page dashboard.
The Dashboard Pruner App only considers active views when determining if a dashboard is stale.

If you determine that one of the dashboards which is identified by the app should not be deleted, you can
simply open the dashboard in the DHIS2 dashboard app to update its last viewed timestamp.This should
have the effect of removing it from the list of dashboards identified as stale by integrity check used
by the Dashboard Pruner App.

## Getting started

### Install dependencies
To install app dependencies:

```
yarn install
```

### Compile to zip
To compile the app to a .zip file that can be installed in DHIS2:

```
yarn run zip
```

### Start dev server
To start the webpack development server:

```
yarn start
```

By default, webpack will start on port 8081, and assumes DHIS2 is running on 
http://localhost:8080/dhis with `admin:district` as the user and password.

A different DHIS2 instance can be used to develop against by adding a `d2auth.json` file like this:

```
{
    "baseUrl": "localhost:9000/dev",
    "username": "john_doe",
    "password": "District1!"
}
```
