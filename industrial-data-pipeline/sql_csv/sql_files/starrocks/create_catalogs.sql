DROP CATALOG IF EXISTS mysql_catalog;

CREATE EXTERNAL CATALOG mysql_catalog
PROPERTIES (
    "type" = "jdbc",
    "user" = "user",
    "password" = "userpassword",
    "jdbc_uri" = "jdbc:mysql://host.docker.internal:3306?useSSL=false&allowPublicKeyRetrieval=true",
    "driver_name" = "mysql",
    "driver_class" = "com.mysql.cj.jdbc.Driver",
    "driver_url" = "file:///data/deploy/starrocks/fe/lib/mysql-connector-j-8.0.33.jar"
);

-- Use the catalog
SET CATALOG mysql_catalog;