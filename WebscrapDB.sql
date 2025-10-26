-- Create database
CREATE DATABASE WebScrapingDB;
GO

-- Use the database
USE WebScrapingDB;
GO

-- Create table to store search results
CREATE TABLE SearchResponses (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_query NVARCHAR(500) NOT NULL,
    source_link NVARCHAR(MAX),
    content NVARCHAR(MAX),
    timestamp DATETIME DEFAULT GETDATE()
);

select * from SearchResponses